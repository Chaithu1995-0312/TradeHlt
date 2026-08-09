# Model Integration Audit — Draft (2026-07-20)

**Status:** START of model-layer architecture work.  
**CRT state engine:** treated as **characterized** (topology + predicates + regime ablations).  
**Authority:** architecture / dataflow only — no economic claims.  
**Active config:** `v2_multi_2026_04`.

**Runtime grounding (mandatory for every model card below):**  
[`backtest-runner-runtime-call-graph-2026-07-20.md`](backtest-runner-runtime-call-graph-2026-07-20.md)  
— full `BacktestRunner` → `CRTEngine` → optional `EngineRunner` call graph + `_feat_map_er` / `_er_context` key inventory. Do not audit models from package layout alone.

---

## 0. Separation of concerns (agree with the assessment)

| Layer | What we understand | Remaining gap |
|---|---|---|
| **Feature layer** | HOW/WHAT, freeze, vector pin | Future programs only |
| **CRT state engine** | Topology, predicates, failure census, guard ablations | Bugs only |
| **Model / fusion stack** | Partially (this audit starts here) | End-to-end consumers of CRT **vs** features |

**Critical naming split (do not conflate):**

| Name in code | What it actually is |
|---|---|
| `CRTEngine` / `crt_engine_v2` | **State machine** (RANGE…EXECUTION). Authoritative for structure. |
| `engines.crt_engine.compute` / fusion key `"crt"` | **Score wrapper** over `compute_scores()` using **features** (`body_ratio`, `disp_strength`, `retest_depth`, …). **Not** the state enum. |

Understanding states ≠ understanding the fusion `"crt"` score.

---

## 1. Two spines (architecture fact)

```text
SPINE A — Structure / admission (always in backtest CRT path)
  OHLCV
    → CRTEngine (state machine)     [crt_engine_v2]
    → session / score / soft-conf / risk  (inside CRT path)
    → TRADE_OPENED  (or FILTER_REJECTED / reset)

SPINE B — Fusion gate (EngineRunner; live always; backtest only if BACKTEST_ENGINE_GATE=1)
  OHLCV + FeaturePipeline / feeder features
    → EngineRunner.run(input_data, context)
         → zone_gate (BitNet zone registry scores)
         → crt_compute  (feature score, NOT state enum)
         → gaussian.compute(features)
         → rr.compute(OHLC polarity)
         → [rr_fusion if enabled — OFF on active config]
         → FusionEngine.compute(weights)
         → DecisionEngine / belief / dual-engine / …
    → APPROVE | REJECT
```

On **active patch**, research/backtest often runs **Spine A only** (`BACKTEST_ENGINE_GATE=0`).  
Live path: Spine A then Spine B (and planner / Ultron).

---

## 2. Model cards (four questions each)

### 2.1 CRT state engine (`config_layer.crt_engine_v2.CRTEngine`)

| Q | Answer |
|---|---|
| **Inputs** | OHLCV candles; HTF range refs; local `atr_abs` (not canonical close-relative atr); config thresholds |
| **Logic** | Rule state machine (`VALID_TRANSITIONS` + `try_*` guards) |
| **Outputs** | `current_state`, events, optional trade candidate, cached CRT features at RETEST |
| **Consumers** | Backtest journal; live_engine_hook after RETEST/EXECUTION; **not** directly FusionEngine |
| **Active?** | **Yes — load-bearing** for trade structure |

### 2.2 Fusion “CRT” score (`engines.crt_engine.compute` → `scoring_engine.compute_scores`)

| Q | Answer |
|---|---|
| **Inputs** | Features: `body_ratio`, `disp_strength`, `atr`, `retest_depth`, `candles_since_retest`, `sweep_detected`, `double_sweep`; HOW weights from context |
| **Logic** | Weighted rule score (not state enum) |
| **Outputs** | `{score: float}` under engine key `"crt"` |
| **Consumers** | `FusionEngine` (weight_crt **0.4** on active config) |
| **Active?** | **Yes when EngineRunner runs** |
| **Deep audit** | **§7** |

### 2.3 ZoneGate (`zone_gate` + `BitNetZoneGate` registry)

| Q | Answer |
|---|---|
| **Inputs** | Full 38 CANONICAL keys from `_feat_map_er`; registry `models/zone_registry.json` (8 zones) |
| **Logic** | Per-zone Gaussian similarity → top-k cluster score vs `zone_cluster_threshold=0.25` |
| **Outputs** | score → fusion weight **0.2**; `passed` only in `meta` (see MI-ZG-01) |
| **Consumers** | FusionEngine; intended DE hard veto (wiring defect §6.5); backtest bypasses `zone_gate_invalid` by default |
| **Uses CRT state enum?** | **No** |
| **Active?** | **Yes when EngineRunner runs** (`zone_mode=hard`) |
| **Deep audit** | **§6** |

### 2.4 Gaussian (`HeuristicGaussianEngine` on active config)

| Q | Answer |
|---|---|
| **Inputs** | **Only** `ema_fast`, `ema_slow`, `momentum_score` (pipeline 9/21 EMA + ATR-scaled momentum). `direction` accepted but **ignored** on heuristic. |
| **Logic** | 1D kernel: \(x=(r+\tanh m)/2\), \(s=\exp(-(x-\mu)^2/(2\sigma^2))\); default \(\mu{=}0,\sigma{=}1\) |
| **Outputs** | `{score∈(0,1], reason, meta{mu,sigma,x}}` under fusion key `"gaussian"` |
| **Consumers** | Fusion weight **0.2**; **also** DecisionEngine `p_win` (threshold **0.4**); evaluate-path adapter (shadow unless `fusion_use_evaluate`) |
| **Uses CRT state enum?** | **No**. Direction from CRT does **not** change heuristic score. |
| **Active?** | **Yes** (`gaussian_impl=heuristic`). ML track inert unless `ml` / `shadow_ml`. |
| **Deep audit** | **§9** |

### 2.5 RR Engine (`engines.rr_engine.RREngine`) — Candle Polarity Index

| Q | Answer |
|---|---|
| **Inputs** | Same-candle `high`, `low`, `close` only |
| **Logic** | CPI: `max((h−c)/(h−l), (c−l)/(h−l))` — close commitment to extremes (**not** forward RR) |
| **Outputs** | `{score, candle_polarity, rr_ratio alias, semantic}` → fusion `"rr"` |
| **Consumers** | Fusion weight **0.2**; DE economic RR **skipped** when `rr_semantic=candle_polarity` (F-048 fix); Ultron true RR is **separate** (not this engine; not on BacktestRunner) |
| **Uses CRT state enum?** | **No** |
| **Active?** | **Yes** (EXPECTED_ENGINES). **rr_fusion** inert (`enabled:false`, F-038) |
| **Deep audit** | **§10** |

### 2.6 BitNet

| Q | Answer |
|---|---|
| **Inputs** | Canonical / CRT-mapped features when enabled; zone path uses registry |
| **Logic** | Neural hard-reject / zone scoring |
| **Outputs** | Score / zone check |
| **Consumers** | Zone scoring path in EngineRunner; main gate when `use_bitnet` |
| **Active on patch?** | **INERT for main hard-reject** (`use_bitnet` not true / F-004); zone registry still used for ZoneGate scores |

### 2.7 TradeNet (`tradenet_meta_engine`)

| Q | Answer |
|---|---|
| **Inputs** | Designed for fusion neural slot |
| **Logic** | Meta / neural (when wired) |
| **Outputs** | Score for fusion neural component |
| **Consumers** | Fusion evaluate path if neural wired |
| **Active on patch?** | **UNWIRED / stub** (F-005) — not in EXPECTED_ENGINES |

### 2.8 FusionEngine

| Q | Answer |
|---|---|
| **Inputs** | `engine_results` dict: crt / gaussian / zone_gate / rr scores (+ optional strategy_consensus) |
| **Logic** | Weighted fusion; optional conflict policy; optional evaluate() LLM band |
| **Outputs** | `final_score`, accept/reject vs `fusion_min_score` |
| **Consumers** | DecisionEngine path, belief gate, dual-engine, live planner handoff |
| **Active?** | **Yes when EngineRunner runs** |

### 2.9 ExecutionPlanner + UltronRiskGate

| Q | Answer |
|---|---|
| **Inputs** | Accepted decision / trade plan fields; CRT-derived SL/TP geometry on CRT path |
| **Logic** | Planner: entry/SL/TP/TTL; Ultron: true RR, risk %, gates |
| **Outputs** | Plan / APPROVE|REJECT |
| **Consumers** | Live execution / alerts |
| **Uses CRT?** | **Yes** on CRT spine (prices/state); fusion path is separate admission |

---

## 3. Dependency map (what is actually passed)

```text
OHLCV ─────────────────────────────────────────────────────────┐
  │                                                            │
  ├─► FeaturePipeline ──► 38-dim features / feeder dict        │
  │         │                                                  │
  │         │  (body_ratio, retest_depth, ema_*, atr, …)     │
  │         ▼                                                  │
  │   ┌─────────────────────────────────────┐                │
  │   │ EngineRunner (gate ON / live)       │                │
  │   │  zone_gate(features)                │                │
  │   │  crt_score(features)  ← NOT state   │                │
  │   │  gaussian(features)                 │                │
  │   │  rr(OHLC polarity)                  │                │
  │   │  → Fusion → Decision…               │                │
  │   └─────────────────────────────────────┘                │
  │                                                            │
  └─► CRTEngine state machine ◄────────────────────────────────┘
            │  states + local atr_abs + range
            ▼
      session / CRT score / soft-conf
            ▼
      TRADE_OPENED ──► journal / planner / Ultron (live)
```

**Redundancy risk (most likely failure mode):**  
Several fusion engines re-score **candle geometry** (body, displacement-like features, polarity) that **partially overlaps** CRT structure, without reading `CRTState`. They can look independent while encoding related information.

---

## 4. Active-config truth (v2_multi_2026_04)

| Component | Status on active patch |
|---|---|
| CRT state machine | **ON** (structure spine) |
| EngineRunner 4-engine fusion | **Live ON**; **backtest default ON** (`BACKTEST_ENGINE_GATE` default `"1"`; set `0` for CRT-only) |
| gaussian_impl | **heuristic** |
| rr_fusion | **enabled: false** |
| use_bitnet (main gate) | **false / inert** (F-004) |
| TradeNet | **unwired** (F-005) |
| Fusion weights | crt 0.4 · gaussian 0.2 · zone 0.2 · rr 0.2 |

---

## 5. What is complete vs next work

### Complete (stop unless bug)

- Feature freeze + XAUUSD feature pin  
- CRT topology + predicates + failure census + multi-regime guard ablations  
- Runtime benchmark suite authority (separate from feature freeze)  
- **BacktestRunner call graph + context inventory** (grounding doc)  
- **ZoneGate deep audit** (§6)  
- **Fusion CRT Score Engine deep audit** (§7)  
- **Gaussian heuristic deep audit** (§9)  
- **RR polarity engine deep audit** (§10)
- **FusionEngine + DecisionEngine joint audit** (§11)

### Next (model integration program)

1. ~~EngineRunner contract~~ → see call-graph doc  
2. ~~ZoneGate~~ → §6  
3. ~~CRT Score Engine~~ → §7  
4. ~~Gaussian heuristic~~ → §9  
5. ~~RR polarity~~ → §10  
6. ~~Fusion + DecisionEngine~~ → §11 (end-to-end admission closed for BacktestRunner ER path)  
7. BitNet / TradeNet inert confirmation (optional)  
8. Optional governed fixes: DE zone.valid wire (MI-ZG-01); consider bypass interaction with DE short-circuit |

---

## 6. ZoneGate deep audit (execution-path grounded)

**Grounding:** call graph §2.5 / ER step 2 — only on `TRADE_OPENED` after adapter when gate ON.  
**Prior lineage (observational):** [`docs/governance/zonegate_lineage_audit.md`](../governance/zonegate_lineage_audit.md) (ACTIVE_GEOMETRIC + NO_MARGINAL_VALUE).  
**This section adds:** exact handoff keys, dual-threshold mechanics, and a **DecisionEngine wiring defect** that changes how “hard gate” actually behaves.

### 6.1 Position on the path

```text
BacktestRunner TRADE_OPENED
  → TrapValidator (adapter)          # hard pre-gate; not ZoneGate
  → run_zone_gate_engine(...)        # FIRST of the four EXPECTED engines
       model_fn = BitNetZoneGate.check → top_scores
                → compute_weighted_cluster_score
       threshold = zone_cluster_threshold (0.25)
  → engine_results["zone_gate"] = {score, direction, meta}
  → FusionEngine (weight_zone_gate = 0.2)
  → … fusion_min_score …
  → DecisionEngine.evaluate(zone_gate={valid, score})
```

ZoneGate is **not** first overall (adapter is), but it is the **first major evidence model** among the four fusion engines and the only one with a registry-backed geometric prior.

### 6.2 Inputs actually received (from `_feat_map_er` + context merge)

| Layer | Keys | Source at TRADE_OPENED |
|---|---|---|
| Vector contract | Full `CANONICAL_FEATURE_ORDER` (38) | `filter_canonical_inputs` — **missing any key → ValueError → block** (score 0, passed False) |
| Primary geometry | 38 floats incl. OHLCV, body_ratio, disp_strength, retest_depth, ema_*, session, … | FeaturePipeline row at candle ts |
| Registry | `models/zone_registry.json` | `schema_version=v2_gaussian`, **8 zones**, μ/σ/w length **38**, total training weight **139,942** |
| Soft extras | `zone_distance` / `zone_freshness` / `zone_strength` | Only used if `zone_mode=soft` (active = **hard**) |
| **CRTState** | — | **Never** |
| CRT `cached_features` / FM-027/028 | — | **Never** (pipeline names only) |

**Config knobs (active `v2_multi_2026_04`):**

| Key | Value | Role |
|---|---|---|
| `zone_registry_path` | `models/zone_registry.json` | Runtime centroids |
| `zone_mode` | `hard` | Soft score override OFF |
| `zone_gate_execution_mode` | `normal` | not `force_pass` |
| `zone_cluster_threshold` | **0.25** | Score ≥ T ⇒ `passed` inside `run_zone_gate_engine` |
| `zone_gate.top_k` | 3 | top_scores length |
| `zone_gate.cluster_min_n` | 2 | need ≥2 scores for cluster formula |
| `zone_gate.cluster_spread_max` | 0.15 | spread > max ⇒ cluster score **0** |
| `zone_min_samples` | 50 | underpowered auto-bypass (registry ≫ 50) |
| `fusion_engine.weight_zone_gate` | **0.2** | Fusion contribution |

### 6.3 Logic (two nested score systems — do not conflate)

**A. Per-zone similarity (`BitNetZoneGate.check`)**  
For each of 8 zones:  
`score_z = Σ w_i · exp(−½ ((x_i−μ_i)/σ_i)²) / Σ w_i` over 38 dims.  
Also computes per-zone `allowed` vs **zone-local** `threshold` field — **BYPASSED by the live spine** (comment in `live_engine.py:286–290`). Spine only consumes **`top_scores`**.

**B. Cluster aggregation (`_zone_model_fn` in EngineRunner)**  
```text
top_scores = top_k similarities
if len(top_scores) >= cluster_min_n:
    score = compute_weighted_cluster_score(top_scores, spread_max)
      # <2 → max; spread>spread_max → 0; else Σ (s/total)*s
else:
    score = best zone score (fallback)
on exception → 0.5 (neutral, non-blocking)
```

**C. Gate boolean (`run_zone_gate_engine`)**  
`passed = (score >= zone_cluster_threshold)` under `execution_mode=normal`.  
Returns `{score, passed, vector, valid: passed}`.

**D. Soft mode** (inactive): replaces **score only**; does not redefine hard pass logic upstream of fusion if hard path already ran — active config is hard.

### 6.4 Outputs and consumers

| Output field | Where written | Who reads it |
|---|---|---|
| `zone_raw.score` | `run_zone_gate_engine` | → `zone_result.score` → **FusionEngine** (0.2) |
| `zone_raw.passed` | same | → `zone_result.direction` only (1/0) |
| `zone_result` package | EngineRunner | completeness key `"zone_gate"`; audit; cognitive bus |
| DE `zone_gate.valid` | **intended** hard veto | **see §6.5 wiring defect** |
| DE `zone_gate.score` | DecisionEngine | not primary hard gate (score path uses fusion score) |

**Reject paths that can involve ZoneGate:**

| Stage | Condition | Backtest admission effect |
|---|---|---|
| Vector / scoring error | extraction fails | `passed=False`, score 0 → feeds fusion low + DE path |
| Cluster spread | spread > 0.15 | score 0 → below 0.25 → passed False |
| Score &lt; 0.25 | hard threshold | passed False |
| Fusion low | final_score &lt; 0.25 (incl. weak zone weight) | REJECT `low_fusion_score` — **not** bypassed |
| DE `zone_gate_invalid` | `valid` false | REJECT reason — **bypassed by default** in backtest (`BACKTEST_BYPASS_ZONE_INVALID=1`) |
| Empty registry | fail-open allowed/score | non-blocking |
| Underpowered | auto allow score 1.0 | N/A for current 139k-weight registry |

### 6.5 STRUCTURAL FINDING — DecisionEngine never sees `passed`

**Code (verified):**

```text
zone_result = {
  "engine": "zone_gate",
  "score": zone_raw["score"],
  "direction": 1 if zone_raw["passed"] else 0,   # ← passed used here
  "meta": zone_raw,                              # ← passed lives only inside meta
  # NO top-level "passed"
}

zone_gate_ctx = {
  "valid": bool(zone_result.get("passed", False)),  # ← always False
  "score": zone_result["score"],
}
```

`DecisionEngine.evaluate` then:

```text
if not zone_gate_dead and not zone_gate["valid"]:
    reject("zone_gate_invalid")
```

**Consequence (Certain, architecture):**

1. Any ER path that reaches DecisionEngine with `zone_gate_dead=false` is **structurally** eligible for `zone_gate_invalid`, **independent of geometric score**.  
2. Default **backtest** sets `BACKTEST_BYPASS_ZONE_INVALID=1` and treats that reason as non-veto → **journal can still open**.  
3. Therefore, in default gate-ON **backtest**, ZoneGate’s hard **boolean** does **not** control admission; only (a) fusion score contribution, (b) earlier rejects, (c) non-bypassed DE reasons matter.  
4. Live path (no bypass) would **hard-reject every** DE evaluation with `zone_gate_invalid` until wiring is fixed **or** `zone_gate_dead` is set — this is a **live-path risk** (aligns with F-010 / “live unverified” class; do not claim production loss without live trace).  
5. Explains part of why zone **weight** ablations can look inert for **entry identity** (F-036) when measurement rides the backtest bypass: boolean gate is short-circuited; score weight is the only remaining lever and was non-pivotal under that experiment.

**Correct wire (documentation only — no fix in this turn):**  
`valid` should read `zone_raw.get("passed")` or `zone_result["meta"]["passed"]` or promote `"passed"` onto `zone_result`.

### 6.6 Independence from CRT structure

| Question | Answer |
|---|---|
| Trained on CRT TRADE_OPENED only? | **No** — KMeans on opportunities stream (~140k; F-022 class for **labels**, geometry μ still real) |
| Shares features with CRT risk score? | **Partial** — body_ratio / disp / retest names overlap CRT cache themes but **pipeline** definitions + full 38-dim |
| Uses range high/low / sweep geometry? | **No** direct CRT geometry |
| Can reject a perfect CRT path? | Intended yes via score/threshold; **boolean path broken/bypassed as above** |
| Economic edge of zones? | F-041B: 0/8 honest E>0; F-036: ΔG001≡0 for weight/threshold grid |

### 6.7 ZoneGate audit card (fill checklist)

| Field | Fill |
|---|---|
| Call site | `EngineRunner.run` after adapter; `run_zone_gate_engine` + `BitNetZoneGate.check` |
| Cadence | TRADE_OPENED only (backtest gate-ON); not every bar |
| Required keys | All 38 CANONICAL keys present in input dict |
| CRTState used? | **No** |
| Reject effect | Score → fusion (soft). Boolean → DE `zone_gate_invalid` (**wired dead / backtest bypassed**). Vector error → score 0. |
| Active config | ON, hard, threshold 0.25, weight 0.2, 8 zones loaded |
| Open truth risks | DE `passed` key drop; dual threshold (zone-local vs bitnet_zone); name collision BitNetZoneGate ≠ BitNet neural; relative atr inside 38-dim |

**Authority:** architecture / wiring. **No** retrain/promote authority from this audit. F-036/F-041 remain economic priors.

---

## 7. Fusion CRT Score Engine deep audit

**Not** `CRTEngine` / `CRTState`. This is `engines.crt_engine.compute` → `scoring_engine.compute_scores`, fusion key `"crt"`, **highest fusion weight (0.4)**.

### 7.1 Position on the path

```text
EngineRunner after adapter (parallel stage with zone/gaussian/rr)
  crt_compute(
    trade_id="Test:",                    # placeholder; not trade id
    features=input_data,                 # same _feat_map_er as ZoneGate
    context={score_component_weights: HOW 4-tuple from prod crt_engine}
  )
  → engine_results["crt"] = {score} | {score:0, reason}
  → FusionEngine weight_crt = 0.4
```

Runs **unconditionally** once adapter passes; does **not** read zone result.

### 7.2 Inputs actually received

| Input | Source in `_feat_map_er` | Semantic |
|---|---|---|
| `body_ratio` | pipeline 38-dim | body/range ∈[0,1] (canonical candle_math) |
| `disp_strength` | pipeline FM-020 | body/(atr·close) style displacement strength |
| `atr` | **pipeline close-relative atr** | **not** CRT `state.atr_abs` (setdefault cannot override) |
| `retest_depth` | pipeline FM-021 | \|close−ema_fast\|/(atr·close) when retest flag |
| `candles_since_retest` | pipeline int | time since retest flag |
| `sweep_detected` | pipeline bool/float | pipeline sweep flag — **not** CRT sweep event |
| `double_sweep` | pipeline | pipeline double-sweep flag |
| `score_component_weights` | prod `crt_engine.score_component_weights` | **(0.35, 0.25, 0.20, 0.20)** = (sweep, breakout, retest, time) |

**Not consumed:** `CRTState`, direction, HTF range, SL/TP, zone score, gaussian score.

Missing weights → PLAN-002 fail path (caller must inject; ER does). Feature KeyError → `{score: 0.0, reason}` soft into fusion.

### 7.3 Logic (as-wired formula)

From `scoring_engine.compute_scores`:

```text
disp_strength_atr_rescale = move / atr          # FM-029; move := pipeline disp_strength
s_sweep   = 0 if !sweep else (1.0 if double_sweep else 0.7)
s_breakout = 0.5*min(body_ratio,1) + 0.5*min(disp_strength_atr_rescale/2, 1)
s_retest  = exp(−(retest_depth − 0.5)² / 0.04)   # peaks at depth=0.5
s_time    = exp(−λ * candles_since_retest)       # λ=0.05 default
s_final   = w_s*s_sweep + w_b*s_breakout + w_r*s_retest + w_t*s_time
```

Active weights: **0.35 / 0.25 / 0.20 / 0.20**.

**Identity note (documented in derived_math):**  
`disp_strength_atr_rescale = disp_strength / atr` is a **third** quantity (FM-029), distinct from FM-020 and CRT FM-028. If both `disp_strength` and `atr` are already ATR-relative, this is a **double-scale** as-wired behavior (tracked as FU-CRT-MOVE-MISWIRE style note) — frozen as current math, not “true displacement ATR.”

**Sweep component risk:** On TRADE_OPENED bars, pipeline `sweep_detected` may be 0 even when CRT path had a structural sweep earlier → **s_sweep often 0** → 35% of fusion-CRT mass can be zero for structural candidates. (Hypothesis-strength: **Likely** mechanism; confirm with one gate-ON feature dump on RETEST/OPEN bars.)

### 7.4 Outputs and consumers

| Output | Consumer |
|---|---|
| `{score: s_final}` | FusionEngine as `"crt"` @ **0.4** — largest single engine weight |
| Exception path `{score:0, reason}` | Same, pulls fusion down |
| Logs | coin-scoped crt_engine JSON line |

**Does not** gate alone. Affects:

1. `FusionEngine.final_score` vs `dual_engine.fusion_min_score` (0.25)  
2. Downstream DE `effective_score` / dynamic threshold / `weak_component`  
3. Belief tracker (post-fusion score), if enabled  

No direct DE “crt_invalid” check.

### 7.5 CRT Score vs CRT state machine (separation table)

| | CRT state machine | Fusion CRT score |
|---|---|---|
| Module | `crt_engine_v2.CRTEngine` | `engines.crt_engine.compute` |
| Cadence | every bar | TRADE_OPENED ER only |
| ATR | absolute `atr_abs` | pipeline relative `atr` |
| Features | `cached_features` at RETEST | pipeline 38 snapshot |
| Role | structure + build trade | fusion evidence weight 0.4 |
| Session | CRT string windows | not used in formula |
| Failure | RISK_REJECTED / no TRADE_OPENED | score 0 into fusion |

**Redundancy:** Both use body/displacement/retest *themes*, but **different definitions and times**. Fusion CRT is **not** a re-encode of `VALID_TRANSITIONS` success — it re-scores pipeline morphology at open.

### 7.6 CRT Score audit card

| Field | Fill |
|---|---|
| Call site | `EngineRunner.run` → `crt_compute` |
| Cadence | TRADE_OPENED / ER call only |
| Required keys | body_ratio, disp_strength, atr, retest_depth, double_sweep (+ weights in context) |
| CRTState used? | **No** |
| Reject effect | Soft zero into fusion only (no dedicated hard stage) |
| Active config | ON whenever ER runs; weight **0.4**; weights (0.35,0.25,0.2,0.2) |
| Open truth risks | relative atr; FM-029 double-scale; pipeline sweep flags ≠ CRT sweep; highest weight on non-state score |

### 7.7 Interaction: ZoneGate + CRT score together

```text
final_score ≈ 0.4·crt + 0.2·zone + 0.2·gauss + 0.2·rr   (regime may adapt weights)
```

- CRT score can dominate (2× any other single engine).  
- Zone boolean currently **does not** veto in default backtest (§6.5); zone **score** still moves the 0.2 term.  
- A high structural CRT path with **pipeline** sweep=0 and middling morphology can still produce modest fusion-CRT; zone geometric neighborhood is independent.  
- F-036: changing zone weight alone did not change entries under gate-ON measurement — consistent with non-pivotal score + boolean bypass.

---

## 8. Ordered findings for subsequent audits

| ID | Finding | Conf | Blocks |
|---|---|---|---|
| MI-ZG-01 | DE reads `zone_result["passed"]` but ER never sets it → structural `zone_gate_invalid` | Certain | Live DE honesty; interpret backtest bypass carefully |
| MI-ZG-02 | Spine uses cluster score vs 0.25; per-zone thresholds are decorative on spine | Certain | — |
| MI-ZG-03 | Zone trained on opportunities, scores full 38-dim, no CRTState | Certain | Independence claims |
| MI-CRT-01 | Fusion CRT weight 0.4 is feature rule score, not state | Certain | Naming / analysis |
| MI-CRT-02 | Uses pipeline atr + FM-029 move/atr rescale (not CRT atr_abs) | Certain | Formula interpretation |
| MI-CRT-03 | Sweep leg may be zero on TRADE_OPENED if pipeline flags off | Likely | Needs one dump to promote Certain |
| MI-G-01 | Live fusion Gaussian = 3-feature heuristic kernel; ML NB artifact not in score path | Certain | — |
| MI-G-02 | Registry entries lack mu/sigma → effective **μ=0, σ=1** (or load-fail defaults same) | Certain | Calibration claims |
| MI-G-03 | `direction` ignored by heuristic; CRT side does not flip gaussian score | Certain | — |
| MI-G-04 | Gaussian score is reused as DE `p_win` (threshold 0.4) — dual consumer beyond fusion 0.2 | Certain | DE low_probability path |
| MI-G-05 | Incremental vs Zone/CRT: only pure trend-momentum kernel; no body/retest/sweep; partial zone overlap via shared EMA dims | Likely | No ΔG001 claim |
| MI-RR-01 | Live `"rr"` = Candle Polarity Index on H/L/C only; not forward RR | Certain | Naming |
| MI-RR-02 | `rr_fusion` OFF → base polarity only; trained model inert (F-038/F-044/F-045) | Certain | — |
| MI-RR-03 | ER marks `rr_semantic=candle_polarity` → DE **skips** `low_rr` vs 1.5 (F-048 fix held) | Certain | Live execute path |
| MI-RR-04 | Valid non-doji polarity ∈ **[0.5, 1.0]** → fusion component never soft-zero on normal bars | Certain | Fusion floor |
| MI-RR-05 | Incremental: close-in-range commitment; orthogonal to Gaussian; related-but-distinct from CRT `body_ratio` | Certain | — |
| MI-FUS-01 | ER always passes `regime=` into fusion → **regime profiles** used, not static 0.4/0.2/0.2/0.2 scalars (neutral→UNKNOWN 0.30/0.25/0.25/0.20) | Certain | Weight interpretation |
| MI-FUS-02 | ConvergenceController mutates `final_score` (penalty) but its `accepted` flag is **not** an ER hard gate | Certain | — |
| MI-FUS-03 | `normalized_score` computed but **not** passed into DE fusion_ctx → DE uses raw `final_score` | Certain | — |
| MI-FUS-04 | TRENDING/RANGING profiles reserve `strategy_consensus` 0.10; absent consensus → weight mass on zero | Certain | Score ceiling |
| MI-DE-01 | DE reject order: zone_gate_invalid → low_score → low_probability → low_rr → weak_setup | Certain | — |
| MI-DE-02 | With MI-ZG-01 + default BYPASS, DE **always** emits zone_gate_invalid first → other DE checks **never run** on default BT path; bypass then **nullifies DE entirely** for admission | Certain | Architecture |
| MI-DE-03 | Pre-DE gates that still bind: adapter, low_fusion_score (0.25), belief (off), dual/ultron_gate legacy | Certain | Effective admission |
| MI-E2E-01 | Backtest gate-ON admission = CRT TRADE_OPENED ∧ ¬adapter ∧ ¬low_fusion ∧ ¬ultron_legacy ∧ (DE bypassed if only zone_invalid) | Certain | End-to-end |

**Next:** optional BitNet/TradeNet inert confirm; optional fix MI-ZG-01 (restores real DE gates under bypass policy rethink).

---

## 9. Gaussian deep audit (HeuristicGaussianEngine)

**Grounding:** call graph ER step 2; same `_feat_map_er` as ZoneGate/CRT score.  
**Prior lineage:** [`docs/governance/gaussian_lineage_audit.md`](../governance/gaussian_lineage_audit.md) (DUAL_TRACK: live heuristic vs inert ML).  
**Active config:** `gaussian_impl: heuristic`, `fusion_engine.weight_gaussian: 0.2`.

Do **not** conflate with ZoneGate’s per-zone Gaussian similarity (different subsystem).

### 9.1 Runtime invocation

```text
BacktestRunner TRADE_OPENED (BACKTEST_ENGINE_GATE=1)
  → adapter pass
  → EngineRunner constructs self.gaussian = HeuristicGaussianEngine(config)
       config includes instrument from bt_config (e.g. XAUUSD / BNBUSDT)
  → gaussian_result = self.gaussian.compute(input_data, direction=_gauss_dir)
       _gauss_dir = "short" if direction<0 else "long"   # from CRT int
       # heuristic IGNORES direction
  → engine_results["gaussian"] = gaussian_result
  → [shadow_ml only] attach gaussian_result["shadow"] — not fused
  → FusionEngine.compute → weight_gaussian * score
  → DecisionEngine.evaluate(p_win = gaussian.score)   # SECOND consumer
```

| Property | Value |
|---|---|
| Cadence | TRADE_OPENED / ER call only (not every bar) |
| Order among engines | After zone_raw packaging; concurrent logical stage with crt/rr (all before fusion) |
| Depends on Zone/CRT score outputs? | **No** — reads features only |
| `fusion_use_evaluate` | default **false** → primary path is `fusion.compute(engine_results)`, not adapter re-score |
| Exception in `compute` | Bubbles → BacktestRunner ER try/except **fail-open** (trade allowed) |

### 9.2 Exact inputs

| Key | Required? | Source in `_feat_map_er` | Identity |
|---|---|---|---|
| `ema_fast` | **yes** | pipeline 38-dim | Close EWM **span 9** (`feature_pipeline.ema_fast_span`) |
| `ema_slow` | **yes** | pipeline 38-dim | Close EWM **span 21** |
| `momentum_score` | **yes** | pipeline 38-dim | FM-style `close_delta / atr` (ATR-relative) |
| Full dict length | assert `len(input_data) ≥ 38` | 38 + extras (OHLCV already in map, direction, integrity, ts) | Other keys **accepted, ignored** |
| `direction` / `signal_dir` | optional | CRT `engine.state.direction` | **Ignored** by heuristic (`direction` param API-compat only) |
| CRT `ema_fast/slow` (spans 2/5) | — | CRT soft-conf only | **Not** these inputs |
| CRTState / zone score / crt score | — | — | **Not read** |

**Registry / calibration inputs (not features):**

| Source | Role on active path |
|---|---|
| `config["gaussian_mu"|"gaussian_sigma"]` | Optional override — **absent** on active prod JSON |
| `GaussianRegistry` active entry for `instrument` | Intended μ/σ; BNB/ETH entries have **no** `mu`/`sigma` keys → normalize to **0.0 / 1.0** |
| Model JSON under `model_file` | Full NB + scaler for **ML** track — **not** loaded by heuristic |
| Missing instrument (e.g. XAUUSD) in `__active__` | Load fails → registry None → **μ=0, σ=1** defaults |

**Effective live kernel center:** **μ = 0, σ = 1** for practical instruments under current registry shape (Certain for default path).

### 9.3 Mathematical computation

```text
# fail paths before kernel
if ema_fast == ema_slow and momentum == 0.0:
    return score = 0.5   # neutral_synthetic_condition
if ema_slow == 0:
    raise RuntimeError   # → ER fail-open in backtest

ema_diff       = (ema_fast - ema_slow) / ema_slow     # relative EMA gap (price units cancel)
momentum_norm  = tanh(momentum_score)                 # ∈ (-1, 1)
x              = (ema_diff + momentum_norm) / 2       # scalar summary ∈ ℝ

score = exp( - (x - μ)² / (2 σ²) )                    # ∈ (0, 1], =1 at x=μ
```

With **μ=0, σ=1**: `score = exp(−x²/2)`.

| \|x\| | score | vs DE `p_win_threshold=0.4` |
|---|---|---|
| 0 | 1.00 | pass |
| 0.5 | 0.88 | pass |
| 1.0 | 0.61 | pass |
| ≈1.35 | 0.40 | boundary |
| 2.0 | 0.14 | **fail** low_probability |

**Typical micro-structure:** price-level `ema_diff` is often O(10⁻³)–O(10⁻²) while `tanh(momentum)` is O(0.1–1) → **x is momentum-dominated**. Strong ATR-normalized momentum pushes x away from 0 and **lowers** the gaussian score (distance from μ). This is a **“centered trend” kernel**, not “more momentum ⇒ higher score.”

**Not a calibrated P(win):** output is a radial basis similarity to (μ,σ), reused as if probability.

### 9.4 Output contract

| Field | Type | Meaning |
|---|---|---|
| `score` | float, rounded 4 dp | Kernel value ∈ (0,1] (or 0.5 neutral) |
| `reason` | str | `"gaussian_computed"` \| `"neutral_synthetic_condition"` |
| `meta.mu` / `meta.sigma` / `meta.x` | float | Kernel params + latent x (audit) |
| Shadow (only `shadow_ml`) | nested dict | Logged; **never** replaces `score` for fusion |

**Missing feature:** `RuntimeError` (not soft 0).  
**ML track** (`gaussian_impl=ml`): different contract (vector → NB → score) — **inactive** on patch.

### 9.5 Fusion contribution

| Path | Role | Active? |
|---|---|---|
| `FusionEngine.compute` | `final_score += weight_gaussian * score_gaussian` | **Yes** — weight **0.2** (same tier as zone, rr; half of crt 0.4) |
| Regime profiles (if applied) | e.g. RANGING gaussian **0.32**, TRENDING **0.20**, VOLATILE **0.14** | When regime weight path used |
| `fusion_min_score` | 0.25 on `final_score` | Indirect — weak gaussian pulls average down |
| `FusionEngine.evaluate` | Layer-1 via `GaussianAdapter(self.gaussian)` weight `gaussian_weight=0.6` vs neural | **Shadow/compare only** unless `fusion_use_evaluate=true` (default false) |
| **DecisionEngine `p_win`** | `p_win = gaussian.score`; reject `low_probability` if `p_win < 0.4` | **Yes — hard DE gate** (unlike fusion CRT score) |
| Belief tracker | Uses post-fusion score, not raw gaussian alone | If belief enabled |

**Dual-consumer fact (MI-G-04):** Gaussian is the **only** of the three audited engines that feeds both (1) fusion blend and (2) a dedicated DE probability threshold. Zone’s DE boolean is broken/bypassed; CRT score has no DE-specific gate.

### 9.6 Incremental information beyond ZoneGate and CRT Score

| Axis | ZoneGate (§6) | CRT Score (§7) | **Gaussian (§9)** |
|---|---|---|---|
| Feature support | Full **38** dims vs centroids | body, disp, retest, sweep, time | **Only 3:** ema_fast, ema_slow, momentum |
| Geometry family | Historical **neighborhood** | Candle **morphology** + flags | **Trend/momentum** kernel |
| Uses body_ratio / retest / sweep? | Indirect via vector | **Yes** | **No** |
| Uses EMA / momentum? | Yes (subset of 38) | retest uses ema_fast distance; **no** momentum_score in formula | **Yes — exclusive focus** |
| Aggregation | Multi-dim product of Gaussians + top-k cluster | Weighted 4-component rule | **1D** RBF on hand-built x |
| Calibrated to outcomes? | Unsupervised zones | Fixed weights | μ/σ defaults; **not** outcome-calibrated P(win) |
| Hard DE lever | intended zone_gate_invalid (**broken**) | none | **`p_win < 0.4`** |
| Fusion weight | 0.2 | **0.4** | 0.2 |
| CRTState / direction | No | No | No / direction **ignored** |

**What Gaussian can add (incremental, information-theoretic — not economic authority):**

1. **Orthogonal channel to CRT score morphology** — no body_ratio, disp_strength, retest_depth, or sweep flags in the kernel. A candidate with strong CRT morphology but extreme momentum can still be **DE-rejected** via low p_win while fusion-CRT stays high.  
2. **Different use of EMA than ZoneGate** — Zone embeds ema_* inside a 38-dim similarity; Gaussian **collapses** EMA ratio + tanh(momentum) to a single x and scores proximity to 0. Same raw series, different functional.  
3. **Only explicit momentum_score consumer** among the three — Zone may weight that dim; CRT score formula does not take `momentum_score`.  
4. **Not incremental on direction** — ignores CRT side; no long/short asymmetry in heuristic.

**What it does *not* add:**

- No structural CRT path confirmation.  
- No zone-membership alternative (do not treat score as “in-zone”).  
- No true win probability (name / DE field is misleading).  
- No ML NB discrimination while `gaussian_impl=heuristic`.

**Redundancy residual:** Partial overlap with ZoneGate through shared ema_* / momentum dimensions in the 38-vector — **not** byte-equivalent; Zone can pass high cluster score while Gaussian p_win fails (extreme x), and vice versa (mild trend but OOD full-vector zone).

### 9.7 Gaussian audit card

| Field | Fill |
|---|---|
| Call site | `EngineRunner.run` → `HeuristicGaussianEngine.compute` |
| Cadence | TRADE_OPENED only (gate-ON) |
| Required keys | `ema_fast`, `ema_slow`, `momentum_score` (+ dict len ≥ 38) |
| Math | \(x=((e_f-e_s)/e_s + \tanh m)/2\); \(s=\exp(-(x-\mu)^2/(2\sigma^2))\); μ≈0, σ≈1 |
| Output | `{score, reason, meta}` |
| Fusion | weight **0.2** (+ regime profile); evaluate path secondary |
| DE | **`p_win = score` vs 0.4** |
| CRTState? | **No**; direction ignored |
| Incremental vs ZG/CRT | Trend/momentum-only kernel; sole DE p_win source; no morphology/sweep |
| Open risks | p_win misnomer; μ/σ uncalibrated; momentum-dominated x; ER exception fail-open |

### 9.8 Naming hygiene

| Name | This audit? |
|---|---|
| HeuristicGaussianEngine (fusion `"gaussian"`) | **YES** |
| MLGaussianEngine / GaussianNB | No (inert unless config flip) |
| ZoneGate `compute_gaussian_score` | No (§6) |
| Phase-5 `CRTGaussianScorer` / calibrated scorer | No (pre-ER P5 gate; orthogonal) |

---



## 10. RR polarity engine deep audit (`RREngine` = Candle Polarity Index)

**Grounding:** call graph ER step 2 → `self.rr.compute(input_data)`.  
**Prior lineage:** [`docs/governance/rr_lineage_audit.md`](../governance/rr_lineage_audit.md) (THREE_CONTRACTS A/B/C/D).  
**This section:** six-discipline runtime audit of **contract A** (live polarity) and how B/C/D attach.

### Contracts (never conflate)

| ID | Name | Active on BacktestRunner ER path? |
|---|---|---|
| **A** | `RREngine` Candle Polarity Index | **YES** — fusion `"rr"` |
| **B** | `rr_fusion` / NanoInference trained layer | **NO** — `enabled:false` (F-038) |
| **C** | DE `fusion["rr"]` vs `rr_threshold=1.5` as economic RR | **Blocked** when ER sets `rr_semantic=candle_polarity` (F-048 fix) |
| **D** | UltronRiskGate true forward RR (SL/TP) | **Not on BacktestRunner** (planner/Ultron absent); live separate |

### 10.1 Runtime invocation

```text
BacktestRunner TRADE_OPENED (gate ON) → adapter pass
  → … zone, crt_score, gaussian …
  → rr_result = RREngine(config).compute(input_data)     # A
  → base_rr_score = rr_result["score"]
  → if rr_fusion enabled+loaded:                         # B — OFF on active
        mutate rr_result["score"] (clamp [0,1]); attach rr_fusion meta
    else:
        base polarity score unchanged
  → engine_results["rr"] = rr_result
  → FusionEngine: weight_rr * score_rr                   # 0.2
  → DecisionEngine fusion_ctx:
        rr = polarity, rr_semantic = "candle_polarity"   # C skips low_rr
        true_rr omitted
```

| Property | Value |
|---|---|
| Cadence | TRADE_OPENED / ER only |
| Depends on other engines? | **No** for A. B (if on) can read gaussian + features |
| Config used in A | `min_rr` retained on object but **unused** in scoring |
| Fail mode | Soft `{score:0}` on KeyError / bad structure / doji — does **not** raise |

### 10.2 Exact inputs

| Key | Required? | Source | Notes |
|---|---|---|---|
| `high` | yes | candle / pipeline OHLCV in `_feat_map_er` | |
| `low` | yes | same | |
| `close` | yes | same | Entry reference is **this bar's close** (already "past" highs/lows) |
| `open` | no | — | **Not used** |
| Features / ATR / EMA / zone | no | — | **Not used** |
| CRTState / direction / SL/TP | no | — | **Not used** |
| Forward path after entry | no | — | **Cannot** be true RR (module docstring) |

**rr_fusion (B, inert):** would read retest_depth, body_ratio, disp_strength, gaussian scores, session flags / full 38-dim — **not executed** on active config.

### 10.3 Mathematical computation (contract A)

```text
# validity
require high >= close >= low
range = high - low
if range < 1e-9:  return score=0, reason=doji_zero_range

upper = (high - close) / range    # 1 when close at low  (pin from top)
lower = (close - low)  / range    # 1 when close at high (pin from bottom)
polarity = max(upper, lower)      # in [0.5, 1.0] for any close in [low, high]
```

| Close location | polarity | Interpretation |
|---|---|---|
| At high or low | **1.0** | Full extreme commitment |
| Mid-range | **0.5** | Indecision / balanced |
| 75% toward high | **0.75** | Moderate commitment |
| high==low | **0.0** | Degenerate |
| Invalid OHLC order | **0.0** | `invalid_price_structure` |

**Legacy bug (fixed, historical only):** old formula zeroed at extremes; **new** CPI **rewards** extreme closes (aligned with "committed" CRT bars).

**Not computed:** reward/risk, SL distance, TP distance, expectancy.

### 10.4 Output contract

| Field | Value | Role |
|---|---|---|
| `score` | `round(polarity, 4)` | Fusion extract keys `score` / `rr` / `final_score` |
| `candle_polarity` | same | Preferred DE / ER semantic field |
| `rr_ratio` | **alias of polarity** | Legacy name — **not** economic RR |
| `reason` | `candle_polarity:{v}` or error tag | Logging |
| `semantic` | `"candle_structure_quality"` | Documentation in result |
| Soft fail | score/polarity 0, reason set | Fusion drag only |

When B applied (inactive): `score` may be replaced by fused value; `rr_fusion` blob attached — on active path B never runs.

### 10.5 Fusion contribution

| Path | Role | Active? |
|---|---|---|
| `FusionEngine.compute` | `weight_rr * score_rr` | **Yes** — **0.2** on active (`weight_rr`) |
| Regime profiles | e.g. RANGING rr **0.25**, TRENDING **0.20** | When regime weights used |
| `fusion_min_score` (0.25) | Indirect via final_score | Yes |
| DE `low_rr` vs `rr_threshold=1.5` | Would always fail if polarity treated as RR (polarity ≤ 1) | **Skipped**: ER sets `rr_semantic="candle_polarity"` → `_economic_rr_from_fusion` returns **None** |
| DE other | Polarity does not set p_win or zone.valid | — |
| Ultron Check 2 (D) | True RR from SL/TP vs `min_rr_ratio` | **Not** this engine; **not** BacktestRunner |
| `rr_fusion` (B) | Would replace score before fusion | **OFF** |

**Floor effect (MI-RR-04):** On every valid non-doji bar, `score_rr ∈ [0.5, 1.0]`. With weight 0.2, the rr term alone contributes **[0.10, 0.20]** to the unnormalized blend — it rarely collapses fusion by itself unless doji/invalid (score 0 → term 0).

**F-048 historical:** Before semantic skip, DE `low_rr` fired always → 0 executes; **fixed in ER→DE handoff**, not by changing CPI math.

### 10.6 Incremental information beyond ZoneGate, CRT Score, Gaussian

| Axis | ZoneGate | CRT Score | Gaussian | **RR polarity (A)** |
|---|---|---|---|---|
| Inputs | 38-dim | morphology + flags | ema + momentum | **H, L, C only** |
| Family | Historical neighborhood | Structure quality rule | Trend kernel | **Same-bar close location** |
| body_ratio? | via vector | **yes** (breakout term) | no | **no** — close-in-range, not body size |
| Extreme close? | indirect | body/disp favour commitment | no | **direct objective** |
| Forward RR / SLTP? | no | no | no | **no** (name legacy only) |
| DE hard lever | broken zone.valid | none | p_win | **none** (economic RR skipped) |
| Fusion weight | 0.2 | 0.4 | 0.2 | **0.2** |

**What RR polarity adds:**

1. **Pure OHLC close-commitment** — no features, no registry, no EMAs. Fast, deterministic, bar-local.
2. **Distinct from `body_ratio`:** large mid-body bar → high body_ratio, polarity **0.5**; pin bar at extreme → high polarity, body_ratio may be **low**. CRT score rewards body; RR rewards **where close sits in the range**.
3. **Orthogonal to Gaussian** — no shared inputs.
4. **Mostly orthogonal to ZoneGate geometry** — Zone uses full vector; RR only three prices (also present in vector, different functional).
5. **Direction-agnostic** — long and short treated symmetrically (max of both extremes).

**What it does *not* add:**

- True reward:risk or trade quality after entry.
- Path dependence / multi-bar structure (single candle only).
- Any trained discrimination while B is off.
- A DE veto on active ER path (by design after F-048).

**Redundancy residual:** Mild thematic overlap with CRT "committed bar" intent and with Zone OHLC dims; **not** a re-encode of CRT score (different features and formula).

### 10.7 RR audit card

| Field | Fill |
|---|---|
| Call site | `EngineRunner.run` → `RREngine.compute` |
| Cadence | TRADE_OPENED only (gate-ON) |
| Required keys | `high`, `low`, `close` |
| Math | `polarity = max((h-c)/(h-l), (c-l)/(h-l))` in [0.5,1] |
| Output | score / candle_polarity / rr_ratio alias / semantic |
| Fusion | weight **0.2**; component floor ~0.5 on healthy bars |
| DE | economic RR **not** applied to polarity; Ultron D separate |
| CRTState? | **No** |
| Incremental | Close-in-range CPI vs body_ratio / trend / zone neighborhood |
| Open risks | Legacy name `rr_ratio`; B re-enable needs F-044/F-045 discipline; D unmeasured on backtest |

### 10.8 Four-engine evidence map (post RR)

```text
final_score ≈ 0.4·crt_morphology + 0.2·zone_neighborhood
            + 0.2·gauss_trend_kernel + 0.2·rr_close_polarity

DE hard levers that still matter on default gate-ON backtest:
  - fusion_min_score / dynamic low_score
  - gaussian p_win < 0.4
  - weak_setup
  - zone_gate_invalid (fires structurally; BYPASS default)
  - NOT low_rr from polarity (semantic skip)
  - NOT Ultron true RR (no planner on this path)
```

---


## 11. FusionEngine + DecisionEngine joint audit (admission residual)

**Grounding:** `EngineRunner.run` steps 4–7 after four evidence engines; BacktestRunner interprets return at TRADE_OPENED.  
**Companion engines:** §§6–10. **Call graph:** `backtest-runner-runtime-call-graph-2026-07-20.md`.  
**Authority:** architecture / dataflow only.

This is the last major subsystem on the **BacktestRunner ER admission path**. Planner/Ultron remain live-only.

### 11.0 End-to-end stage map (post-evidence)

```text
engine_results {crt, gaussian, zone_gate, rr [, strategy_consensus]}
    │
    ▼
[4]  detect_regime(input_data) → "trend"|"range"|"neutral"
     FusionEngine.compute(engine_results, regime=…)
         → optional conflict reject (final_score=0)
         → weighted sum (regime profile or static)
         → ConvergenceController.apply (score mutate; accepted NOT ER gate)
         → {final_score, normalized_score, scores, zone_gate_dead, …}
     [optional] fusion.evaluate shadow (compare_evaluate=true, use=false)
    │
    ▼
[5]  if final_score < dual_engine.fusion_min_score (0.25)
         → REJECT low_fusion_score
[5b] belief gate (signal_belief.enabled — OFF / absent on active)
[6]  dual breakout+trap → RegimeGovernor | _regime_governor_legacy
         ultron_gate_enabled=false on active → LEGACY
         → REJECT ultron_gate:* if !allow
[7]  DecisionEngine.evaluate(score, p_win, zone_gate, fusion_ctx)
         → decision execute|reject + reason
    │
    ▼
BacktestRunner:
  REJECT|HOLD (except zone_gate_invalid + BYPASS=1) → no journal open
  else → journal.on_trade_opened
```

---

### 11.1 FusionEngine — six disciplines

#### 11.1.1 Runtime invocation

| Property | Value |
|---|---|
| Call site | `EngineRunner.run` after engines assembled |
| Method | `self.fusion.compute(engine_results, regime=current_regime)` |
| Cadence | TRADE_OPENED only (same as ER) |
| Always receives regime? | **Yes** — ER never omits `regime=` |
| evaluate() path | `fusion_use_evaluate=false` → **not** score authority; `fusion_compare_evaluate=true` → shadow only |

#### 11.1.2 Exact inputs

| Input | Source |
|---|---|
| `engine_results["crt"].score` | fusion CRT score §7 |
| `engine_results["gaussian"].score` | heuristic §9 |
| `engine_results["zone_gate"].score` | cluster score §6 |
| `engine_results["rr"].score` | polarity §10 |
| `engine_results["strategy_consensus"]` | optional; only if context had consensus score ≥0 |
| `regime` | `detect_regime`: trend if \|ema_spread\|≥0.15 and \|momentum\|≥0.3; else range if volatility_ratio≤0.8; else **neutral** |
| Directions for conflict | `payload.direction` per engine — **sparse** on active path (see 11.1.3) |

#### 11.1.3 Mathematical computation

**A. Weights (MI-FUS-01 — load-bearing)**

Because ER always passes `regime=`, fusion uses **`regime_fusion_weights`** (dataclass defaults — **not** in prod JSON; not the scalar `weight_*` keys alone):

| detect_regime | profile | crt | gauss | zone | rr | strategy_consensus |
|---|---|---|---|---|---|---|
| `trend` | TRENDING | 0.38 | 0.20 | 0.12 | 0.20 | **0.10** |
| `range` | RANGING | 0.18 | 0.32 | 0.15 | 0.25 | **0.10** |
| `neutral` | UNKNOWN | 0.30 | 0.25 | 0.25 | 0.20 | 0.00 |

Static JSON `weight_crt=0.4` etc. apply only when `regime` is **omitted** — **not** the ER path.

**B. Conflict (conservative policy on active)**

Non-zero `direction` fields among crt/gaussian/zone/rr: if both + and − present → `final_score=0`, reason `directional_conflict`.

On active evidence engines, **direction is rarely a true long/short vote**:

| Engine | direction field |
|---|---|
| crt score | usually absent → 0 |
| gaussian heuristic | absent → 0 |
| zone_gate | **1 if passed else 0** (pass/fail, not side) |
| rr | absent → 0 |

→ directional conflict is **usually inert** unless consensus or other payloads inject ±1.

**C. Weighted sum**

```text
total_w = w_crt + w_g + w_zone + w_rr + w_consensus   # zone w→0 if zone_gate_dead
final_pre = (Σ w_i * score_i) / total_w
```

If TRENDING/RANGING and no strategy_consensus engine result: `score_consensus=0` but **w_consensus=0.10 still in denominator** → up to 10% mass on zero (MI-FUS-04).

**D. ConvergenceController** (always injected in ER)

When warm (≥10 recorded outcomes):

1. zone_gate dampen: score^4 if score>0.5  
2. sigmoid calibrate all four (k=8, t=0.6)  
3. `final = weighted_score * (1 - penalty(variance))`  
4. computes `accepted` vs adaptive threshold + abs floor 0.3  

**MI-FUS-02:** ER does **not** read `accepted`. Only the **mutated final_score** flows to fusion_min_score / DE. Convergence is a **score transformer**, not a named reject stage.

Cold-start: returns weighted_score unchanged (no penalty).

**E. ScoreNormalizer**

Rolling min-max → `normalized_score` on fusion_result. **Not** fed to DE fusion_ctx (MI-FUS-03).

#### 11.1.4 Output contract (`fusion.compute`)

| Field | Role downstream |
|---|---|
| `final_score` | ER step 5 threshold; DE `score` arg; weak_component |
| `normalized_score` | **orphaned** on ER→DE handoff |
| `scores` | audit / logs |
| `missing_engines` | ER hard reject if non-empty |
| `zone_gate_dead` | **not** copied into DE fusion_ctx (DE reads `fusion.zone_gate_dead` — always false unless set) |
| `reason` | only on conflict / missing early returns |
| conv debug | variance, entropy, threshold, accepted — observational |

#### 11.1.5 Fusion contribution (as gate)

| Check | Threshold / rule | Reject reason | Active BT? |
|---|---|---|---|
| Missing engines | any of 4 absent | incomplete / fusion_missing | yes |
| Directional conflict | conservative | final_score 0 → then low_fusion likely | rare |
| **fusion_min_score** | **0.25** | `low_fusion_score` | **yes — binding** |
| Convergence accepted | internal | **not wired** | no as gate |
| evaluate LLM/neural | evaluate path | off for score | shadow only |

#### 11.1.6 Incremental role vs four engines

Fusion is **not** a fifth morphology model. It:

1. **Collapses** four scores to one scalar under **regime-dependent** weights.  
2. **Optionally penalizes** disagreement (convergence).  
3. **Hard-filters** via fusion_min_score before DE.  

It does **not** re-read OHLCV or CRTState.

---

### 11.2 DecisionEngine — six disciplines

#### 11.2.1 Runtime invocation

```text
p_win = gaussian.score
zone_gate_ctx = { valid: zone_result.get("passed")  # MISSING KEY → False
                  score: zone_result.score }
fusion_ctx = {
  rr, rr_semantic="candle_polarity", candle_polarity,
  weak_component = 1.0 - final_score
  # NO normalized_score, NO zone_gate_dead
}
decision.evaluate(score=final_score, p_win, zone_gate_ctx, fusion_ctx, config+adaptive)
→ { decision: execute|reject, reason, confidence, threshold_used, reject_stage }
```

Only reached if steps 5–6 did not already reject.

#### 11.2.2 Exact inputs

| Arg | Source | Active meaning |
|---|---|---|
| `score` | fusion `final_score` (post-convergence) | primary quality scalar |
| `p_win` | gaussian heuristic score | **not** calibrated win prob |
| `zone_gate.valid` | broken wire (§6.5) | **always False** |
| `zone_gate.score` | zone score | unused for hard gate after valid fails |
| `fusion.rr` + semantic | polarity | economic RR **skipped** |
| `fusion.weak_component` | `1 - final_score` | reject if **> 0.4** ⇒ need final_score **≥ 0.6** |
| config thresholds | decision_engine section | see table |

| Config key | Active value |
|---|---|
| p_win_threshold | 0.4 |
| rr_threshold | 1.5 (inert under polarity semantic) |
| score_threshold | 0.45 (superseded by DynamicThreshold for score check) |
| threshold_percentile / min / max | 85 / 0.45 / 0.65 |
| weak_component_threshold | 0.4 |

DynamicThreshold empty history → midpoint **0.55**.

#### 11.2.3 Mathematical / decision logic (ordered)

```text
effective_score = fusion.normalized_score if present else score
                = score on ER path (normalized never injected)

threshold = DynamicThreshold.compute()   # → 0.55 until history

1. if not zone_gate_dead and not zone_gate.valid:
      REJECT zone_gate_invalid          # ALWAYS on ER path (MI-ZG-01)
2. if effective_score < threshold:
      REJECT low_score
3. if p_win < p_win_threshold:
      REJECT low_probability
4. if economic_rr is not None and economic_rr < rr_threshold:
      REJECT low_rr                     # skipped (candle_polarity)
5. if weak_component > weak_component_threshold:
      REJECT weak_setup                 # final_score < 0.6
else:
      EXECUTE all_conditions_met
```

#### 11.2.4 Output contract

| Field | Values |
|---|---|
| `decision` | `"execute"` \| `"reject"` |
| `reason` | zone_gate_invalid / low_score / low_probability / low_rr / weak_setup / all_conditions_met |
| `confidence` | p_win on execute; 0 on reject |
| `threshold_used` | dynamic threshold |
| `reject_stage` | reason string |

ER then sets `reject_stage` to `"decision"` if reject else `"none"`, attaches regime metadata.

#### 11.2.5 Fusion contribution of DE (admission)

| Intended lever | Works on default gate-ON BT? |
|---|---|
| zone_gate_invalid | Fires always, then **BYPASS** → **no veto** |
| low_score | **Unreachable** (short-circuit at 1) |
| low_probability | **Unreachable** |
| low_rr | skipped by design + unreachable |
| weak_setup | **Unreachable** |
| execute | **Unreachable** as a real path |

**MI-DE-02 (Certain):** On default BacktestRunner (`BACKTEST_BYPASS_ZONE_INVALID=1` + MI-ZG-01), DecisionEngine **does not filter trades**. Every candidate that reaches step 7 returns `zone_gate_invalid`, which BT treats as non-veto.

If bypass were off: **every** ER path would reject at DE (zero executes) — same class as historical F-048 low_rr lockout.

If zone.valid were fixed: DE gates would become **real** (score ≥ ~0.55–0.65 dynamic, p_win≥0.4, final_score≥0.6 weak).

#### 11.2.6 Incremental role

DE is the **named final authority** (`execute`/`reject`) but on the **default backtest admission path** it is **semantically null** due to wiring+bypass. The **effective** post-fusion filters are ER steps 5–6, not DE's score/p_win/weak checks.

---

### 11.3 Dual / belief bridges (between Fusion and DE)

| Stage | Active config | Effect |
|---|---|---|
| Belief | `signal_belief` absent → disabled | no HOLD |
| `ultron_gate_enabled` | **false** | `_regime_governor_legacy` |
| Legacy allow | trend→breakout; range→trap; neutral→max(breakout,trap) if ≥ neutral_min 0.45 | |
| Legacy reject | both dual scores < 0.45; or selected **direction==0** | `ultron_gate:…` / `…_no_direction` |
| Dual inputs | trend_bias, momentum, ema_spread, sweep_detected, disp_strength | **feature** dual engines — not fusion scores |
| CRT direction injection | helps dual direction ≠ 0 | reduces no_direction rejects |

Dual-engine stage **is binding** on backtest and is independent of DE short-circuit.

---

### 11.4 Effective end-to-end admission (gate-ON backtest)

```text
OPEN trade iff:
  CRT produced TRADE_OPENED
  ∧ feature lookup + P5 + drift ok
  ∧ adapter pass
  ∧ four engines ran
  ∧ ¬ directional_conflict (rare)
  ∧ fusion.final_score ≥ 0.25          # after convergence penalty
  ∧ belief approved (or disabled)
  ∧ dual legacy allow (direction ≠ 0, confidence floors)
  ∧ (DE reason is zone_gate_invalid under BYPASS
      OR DE execute if wiring fixed and checks pass
      OR other DE reject → VETO)
```

**Not on path:** ExecutionPlanner, UltronRiskGate true RR, fusion.evaluate authority, DE low_score/p_win/weak under current wire+bypass.

```text
Spine A:  OHLCV → CRT state machine → TRADE_OPENED candidate
Spine B:  features → adapter → 4 evidence scores
            → Fusion (regime weights + convergence) → fusion_min_score
            → dual legacy gate
            → DE (intended final; practically bypassed on default BT)
            → journal open / reject
```

---

### 11.5 Joint audit cards

**FusionEngine**

| Field | Fill |
|---|---|
| Call site | `EngineRunner` step 4 `fusion.compute` |
| Inputs | 4 scores + optional consensus; regime label |
| Math | regime-weighted mean → convergence penalty → final_score |
| Hard gate | fusion_min_score **0.25** (ER step 5) |
| Open risks | regime profiles ≠ JSON scalars; consensus weight hole; normalized orphan |

**DecisionEngine**

| Field | Fill |
|---|---|
| Call site | `EngineRunner` step 7 |
| Inputs | final_score, gaussian p_win, zone.valid (broken), weak_component |
| Math | ordered hard rejects |
| Hard gate on default BT | **nullified** (zone_invalid + bypass) |
| Open risks | MI-ZG-01; fixing valid without rethinking bypass flips all DE gates on |

**Together**

| Field | Fill |
|---|---|
| Completes ER admission? | **Yes** for understanding; **effective** filters ≠ DE checklist |
| Binding post-evidence | fusion_min_score + dual legacy (+ adapter earlier) |
| Cosmetic / bypassed | DE score/p_win/weak under default BT |

---

### 11.6 Program status — BacktestRunner execution architecture

| Layer | Status |
|---|---|
| Feature batch + CRT spine A | Characterized + call graph |
| Evidence: Zone / CRT score / Gaussian / RR | §§6–10 |
| Fusion + DE + dual bridge | **§11** |
| Live-only Planner / Ultron | Out of scope for this BT graph |
| Optional inert BitNet / TradeNet | Confirm-only residual |

**End-to-end understanding of gate-ON BacktestRunner admission is now path-complete**, with open **wiring truths** (MI-ZG-01, MI-DE-02) explicitly named rather than assumed working.

---

## 6. Assessment of the user’s three levels

| Level | Verdict |
|---|---|
| 1 Topology | **Complete** (with SHADOW as RANGE branch, not mid-golden-path) |
| 2 Predicates | **Complete** + empirically ranked |
| 3 Runtime behavior | **Mostly complete** for XAU regimes; optional BNB later |

**CRT is no longer the least-understood subsystem.**  
**Least-understood now: model↔model and model↔CRT **score vs state** coupling.**

---

## 7. Artifacts this program builds on

| Artifact | Role |
|---|---|
| `crt_state_transition_audit_4m.md` | Predicate definitions |
| `predicate_failure_census_6m.md` | Failure modes |
| `guard_ablation_cross_dataset_comparison.md` | Which guards matter across regimes |
| `feature-layer-mutation-freeze-2026-07-20.md` | Feature layer closed for free-form work |
| This doc | Model integration entry point |
