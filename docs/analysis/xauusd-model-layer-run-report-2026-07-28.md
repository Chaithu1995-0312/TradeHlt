# XAUUSD Model Layer Run Report — 2026-07-28

**Authority:** research_only · OBSERVATION_ONLY · no promote
**Corpus:** `D:/Tradelatest/data/mt5/XAUUSD_M15.csv` sha256=`4d73f5cebe33ec91…`
**Config:** `v2_multi_2026_04.json`
**Bars scored:** post-warmup `--limit 200` (full CSV used for FeaturePipeline warmup)
**Created:** 2026-07-28T06:27:26Z

**Refresh note:** includes post-unblock `envelope` (XAU train) and `gaussian_ml` (artifact offline, not gated by `gaussian_impl`); TradeNet 39-dim shadow envelope.

## Executive scoreboard

| Model | Status | Spine | Audit | n_ok | n_err | Notes |
|---|---|---|---|---:|---:|---|
| `bitnet` | **OK** | False | DORMANT | 200 | 0 | 20260728T062748Z |
| `crt_score` | **OK** | True | CONDITIONAL | 200 | 0 | 20260728T062810Z |
| `crt_state_machine` | **OK** | True | CONDITIONAL | 200 | 0 | 20260728T062836Z |
| `engine_runner` | **BLOCKED** | True | ORCHESTRATOR | — | — | Orchestrator — not a single model; use backtest_v2 |
| `envelope` | **OK** | False | EXPERIMENTAL | 200 | 0 | 20260728T062903Z |
| `fusion_compute` | **OK** | True | CONDITIONAL | 200 | 0 | 20260728T062926Z |
| `gaussian` | **OK** | True | FLAWED | 200 | 0 | 20260728T062949Z |
| `gaussian_ml` | **OK** | False | EXPERIMENTAL | 200 | 0 | 20260728T063013Z |
| `llm_gate` | **BLOCKED** | False | FAILED | — | — | EngineRunner never injects llm_fn; fusion_use_evaluate=false |
| `rr` | **OK** | True | CERTIFIED | 200 | 0 | 20260728T063034Z |
| `rr_trained` | **OK** | False | OFF_SPINE | 200 | 0 | 20260728T063056Z |
| `strategies` | **BLOCKED** | False | DEPRECATED | — | — | Sidecar S1-S10; participates_in_live_spine=false |
| `tradenet` | **OK** | False | UNWIRED | 200 | 0 | 20260728T063118Z |
| `zone_gate` | **OK** | True | REDUNDANT | 200 | 0 | 20260728T063139Z |

## Shared substrate (all feature-path models)

```text
data/mt5/XAUUSD_M15.csv
  → normalize OHLCV columns
  → FeaturePipeline.run()  # full corpus warmup
  → build_features(row) → 39-key CANONICAL_FEATURES dict
  → model adapter.score_bar(BarContext)
  → scores.jsonl + manifest.json
```

**Canonical dim:** 39 (schema v4.0).

## Model: `bitnet`

- **Status:** OK
- **Entry:** `bitnet.bitnet_inference.bitnet_score`
- **Spine active:** False
- **Audit tag:** DORMANT
- **Description:** BitNet hard-reject confidence (observe; use_bitnet stays prod value)

### Feature flow

- **inputs:**
  - `body_ratio`
  - `retest_depth`
  - `disp_strength`
  - `atr`
  - `candles_since_retest`
  - `double_sweep`
- **derived:**
  - `legacy6 encoder → MLP backbone → confidence sigmoid`
  - `optional FM-027/028 → retest_depth/disp_strength aliases`
  - `would_reject = confidence < bitnet_main_threshold`
- **outputs:**
  - `confidence`
  - `score`
  - `would_reject`
  - `threshold`
- **note:** `prod use_bitnet remains false; observe only`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\bitnet\XAUUSD\20260728T062748Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.9262487014235211, "mean": 0.7058094308595689, "min": 0.24674400921520445, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.7638782673900071, "std": 0.16937455195755874}}`
- **sample native (first ok bar):**
```json
{
  "confidence": 0.6657193311013094,
  "feature_keys_used": [
    "body_ratio",
    "retest_depth",
    "disp_strength",
    "atr",
    "candles_since_retest",
    "double_sweep"
  ],
  "score": 0.6657193311013094,
  "semantic": "bitnet_hard_reject_confidence",
  "threshold": 0.55,
  "use_bitnet_prod": false,
  "would_reject": false
}
```
- **config keys read:** ['crt_engine.use_bitnet', 'crt_engine.bitnet_main_threshold']

## Model: `crt_score`

- **Status:** OK
- **Entry:** `engines.crt_engine.compute`
- **Spine active:** True
- **Audit tag:** CONDITIONAL
- **Description:** Fusion CRT scorer (compute_scores path; not full FSM)

### Feature flow

- **inputs:**
  - `body_ratio`
  - `disp_strength (as move)`
  - `atr`
  - `retest_depth`
  - `double_sweep`
  - `candles_since_retest`
  - `sweep_detected`
- **derived:**
  - `FM-029 disp_strength_atr_rescale(move, atr)`
  - `s_sweep from sweep_detected/double_sweep`
  - `s_breakout = 0.5*body + 0.5*min(disp_rescale/2,1)`
  - `s_retest = exp(-((depth-0.5)^2)/0.04)`
  - `s_time = exp(-lambda * candles_since_retest)`
  - `final = weighted sum via crt_engine.score_component_weights`
- **outputs:**
  - `score`
- **note:** `NOT UltronRiskEngine linear retest (audit MD-1 dual path)`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\crt_score\XAUUSD\20260728T062810Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.9304, "mean": 0.4079055, "min": 0.156, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.36214999999999997, "std": 0.1717150576383737}}`
- **sample native (first ok bar):**
```json
{
  "score": 0.4503
}
```
- **config keys read:** ['crt_engine.score_component_weights']

## Model: `crt_state_machine`

- **Status:** OK
- **Entry:** `config_layer.crt_engine_v2.CRTEngine.process_candle`
- **Spine active:** True
- **Audit tag:** CONDITIONAL
- **Description:** Full 9-state CRT FSM (sequential candles)

### Feature flow

- **inputs:** `raw OHLCV Candle stream (not 39-dim scorer)`
- **derived:**
  - `RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION`
  - `internal cached_features at RETEST (body_ratio, displacement_*, …)`
  - `BitNet only if use_bitnet (false on active)`
- **outputs:**
  - `state`
  - `action`
  - `trade fields on TRADE_OPENED`
- **note:** `distinct from crt_score fusion path`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\crt_state_machine\XAUUSD\20260728T062836Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.0, "mean": 0.0, "min": 0.0, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.0, "std": 0.0}}`
- **sample native (first ok bar):**
```json
{
  "action": "NONE",
  "candle": "2024-05-22 20:30:00",
  "candle_index": 50,
  "emitted": true,
  "score": 0.0,
  "state": "RANGE",
  "state_after": "RANGE"
}
```
- **config keys read:** ['crt_engine.* via load_prod_config_from_registry']

## Model: `engine_runner`

- **Status:** BLOCKED
- **Entry:** `core.engine_runner.EngineRunner.run`
- **Spine active:** True
- **Audit tag:** ORCHESTRATOR
- **Description:** Full orchestrator — use backtest, not single-model runner

### Feature flow

- **inputs:** `full feature dict + context`
- **outputs:**
  - `fusion + decision package`

**Blocked:** Orchestrator — not a single model; use backtest_v2

## Model: `envelope`

- **Status:** OK
- **Entry:** `research.envelope_offline.shadow.predict_heads`
- **Spine active:** False
- **Audit tag:** EXPERIMENTAL
- **Description:** EnvelopeNet 4 heads (requires --artifact bundle dir); 38-dim legacy vector

### Feature flow

- **inputs:** `38-dim LEGACY_FEATURE_NAMES from live feature dict (drop macd_hist_raw)`
- **derived:**
  - `load envelope_bundle.json + 4 HistGradientBoosting heads`
  - `predict_heads → mfe_r, mae_r_heat, holding_bars, time_to_mfe`
- **outputs:**
  - `mfe_r`
  - `mae_r_heat`
  - `holding_bars`
  - `time_to_mfe`
- **note:** `requires --artifact bundle; XAUUSD train 20260728T062350Z SIGNAL_RETAINED`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\envelope\XAUUSD\20260728T062903Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"n": 0}}`
- **sample native (first ok bar):**
```json
{
  "feature_dim": 38,
  "holding_bars": 20.95472536493347,
  "mae_r_heat": 1.6466882447464375,
  "mfe_r": 1.6536667755550771,
  "semantic": "envelope_heads_observe",
  "time_to_mfe": 12.231523718837344
}
```

## Model: `fusion_compute`

- **Status:** OK
- **Entry:** `core.fusion_engine.FusionEngine.compute`
- **Spine active:** True
- **Audit tag:** CONDITIONAL
- **Description:** Four live engines → FusionEngine.compute only

### Feature flow

- **inputs:** `union of crt_score + gaussian + zone_gate + rr inputs`
- **derived:**
  - `run four engines independently`
  - `FusionEngine.compute weighted average with fusion_engine.weight_*`
  - `optional ScoreNormalizer rolling min-max`
- **outputs:**
  - `final_score`
  - `scores{}`
  - `component_native`
  - `weights_used`
- **not_included:**
  - `DecisionEngine`
  - `ExecutionPlanner`
  - `UltronRiskGate`
  - `neural_fn`
  - `llm_fn`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\fusion_compute\XAUUSD\20260728T062926Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.815, "mean": 0.638663, "min": 0.5048, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.6279, "std": 0.06909461072326842}}`
- **sample native (first ok bar):**
```json
{
  "component_native": {
    "crt": {
      "score": 0.4503
    },
    "gaussian": {
      "meta": {
        "mu": 0.0,
        "sigma": 1.0,
        "x": -0.500984
      },
      "reason": "gaussian_computed",
      "score": 0.8821
    },
    "rr": {
      "candle_polarity": 0.7683,
      "reason": "candle_polarity:0.7683",
      "rr_ratio": 0.7683,
      "score": 0.7683,
      "semantic": "candle_structure_quality"
    },
    "zone_gate": {
      "best_zone_id": "zone_2",
      "cluster_score": 0.6992515509155328,
      "passed": true,
      "score": 0.6992515509155328
    }
  },
  "final_score": 0.6501,
  "missing_engines": [],
  "normalized_score": 0.5,
  "score": 0.6501,
  "scores": {
    "crt": 0.4503,
    "gaussian": 0.8821,
    "rr": 0.7683,
    "zone_gate": 0.6993
  },
  "weights_used": {
    "crt": 0.4,
    "gaussian": 0.2,
    "rr": 0.2,
    "zone_gate": 0.2
  },
  "zone_gate_dead": false
}
```
- **config keys read:** ['crt_engine.score_component_weights', 'engine_runner.gaussian_impl', 'engine_runner.zone_registry_path', 'engine_runner.zone_min_samples', 'engine_runner.zone_cluster_threshold', 'engine_runner.zone_gate_execution_mode', 'engine_runner.zone_gate', 'engine_runner.zone_gate.top_k', 'engine_runner.zone_gate.cluster_min_n', 'engine_runner.zone_gate.cluster_spread_max', 'fusion_engine.weight_crt', 'fusion_engine.weight_gaussian', 'fusion_engine.weight_zone_gate', 'fusion_engine.weight_rr', 'fusion_engine.gaussian_weight', 'fusion_engine.neural_weight', 'fusion_engine.llm_weight', 'fusion_engine.llm_lower_band', 'fusion_engine.llm_upper_band', 'fusion_engine.enable_llm', 'fusion_engine.tier_full', 'fusion_engine.tier_half', 'fusion_engine.tier_quarter', 'fusion_engine.conflict_resolution_policy', 'fusion_engine.min_consensus_signals', 'fusion_engine.min_consensus_agreement']

## Model: `gaussian`

- **Status:** OK
- **Entry:** `engines.heuristic_gaussian_engine.HeuristicGaussianEngine.compute`
- **Spine active:** True
- **Audit tag:** FLAWED
- **Description:** Live heuristic Gaussian kernel (F-060)

### Feature flow

- **inputs:**
  - `ema_fast`
  - `ema_slow`
  - `momentum_score`
- **derived:**
  - `ema_diff = (ema_fast - ema_slow) / ema_slow`
  - `momentum_norm = tanh(momentum_score)`
  - `x = (ema_diff + momentum_norm) / 2`
  - `score = exp(-((x - mu)^2) / (2*sigma^2))  # mu/sigma from registry or engine defaults`
- **outputs:**
  - `score`
  - `reason`
  - `meta{mu,sigma,x}`
- **unused_from_pipeline:** `direction ignored; full dict required by assert only`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\gaussian\XAUUSD\20260728T062949Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.8831, "mean": 0.8824860000000001, "min": 0.8819, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.8825, "std": 0.00029665468140585}}`
- **sample native (first ok bar):**
```json
{
  "meta": {
    "mu": 0.0,
    "sigma": 1.0,
    "x": -0.500984
  },
  "reason": "gaussian_computed",
  "score": 0.8821
}
```
- **config keys read:** ['engine_runner.gaussian_impl']

## Model: `gaussian_ml`

- **Status:** OK
- **Entry:** `training.trainer.load_gaussian_model + NB predict`
- **Spine active:** False
- **Audit tag:** EXPERIMENTAL
- **Description:** Offline GaussianNB — requires --artifact; NOT gated by engine_runner.gaussian_impl

### Feature flow

- **inputs:** `name-anchored feature_schema_resolved from artifact (typically 39)`
- **derived:**
  - `load_gaussian_model(artifact) — NOT engine_runner.gaussian_impl`
  - `scale + predict_expected_rr → logistic score`
- **outputs:**
  - `score`
  - `expected_rr`
  - `confidence`
- **note:** `offline model_id independent of prod gaussian_impl=heuristic`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\gaussian_ml\XAUUSD\20260728T063013Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.6224, "mean": 0.5131275, "min": 0.5, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.5001, "std": 0.03346366975915822}}`
- **sample native (first ok bar):**
```json
{
  "confidence": 0.9373,
  "expected_rr": 0.0314,
  "n_features": 39,
  "prod_gaussian_impl_ignored": true,
  "reason": "ml_gaussian_offline",
  "score": 0.5078,
  "semantic": "gaussian_nb_ml_offline"
}
```

## Model: `llm_gate`

- **Status:** BLOCKED
- **Entry:** `core.fusion_engine.FusionEngine.evaluate`
- **Spine active:** False
- **Audit tag:** FAILED
- **Description:** LLM gate dead — no llm_fn on EngineRunner; evaluate() unused

### Feature flow

- **inputs:** `gaussian/neural scores on evaluate() path`
- **outputs:**
  - `llm blend when score in band`

**Blocked:** EngineRunner never injects llm_fn; fusion_use_evaluate=false

## Model: `rr`

- **Status:** OK
- **Entry:** `engines.rr_engine.RREngine.compute`
- **Spine active:** True
- **Audit tag:** CERTIFIED
- **Description:** Candle polarity index (live fusion RR slot)

### Feature flow

- **inputs:**
  - `high`
  - `low`
  - `close`
- **derived:**
  - `candle_range = high - low`
  - `upper_body = (high - close) / range`
  - `lower_body = (close - low) / range`
  - `polarity = max(upper_body, lower_body)`
- **outputs:**
  - `score`
  - `candle_polarity`
  - `rr_ratio`
  - `semantic=candle_structure_quality`
- **unused_from_pipeline:** `all other 36 canonical features ignored`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\rr\XAUUSD\20260728T063034Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 1.0, "mean": 0.7504040000000001, "min": 0.5032, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.7429, "std": 0.1407640411610863}}`
- **sample native (first ok bar):**
```json
{
  "candle_polarity": 0.7683,
  "reason": "candle_polarity:0.7683",
  "rr_ratio": 0.7683,
  "score": 0.7683,
  "semantic": "candle_structure_quality"
}
```

## Model: `rr_trained`

- **Status:** OK
- **Entry:** `config_layer.rr.rr_pattern_miner.NanoInferenceEngine`
- **Spine active:** False
- **Audit tag:** OFF_SPINE
- **Description:** Trained RR NanoInference (v3 map); not live polarity

### Feature flow

- **inputs:** `39-dim v4 features → explicit v3 38-name map`
- **map:** `macd_hist_z→macd_hist; candle_range→wick_size; drop macd_hist_raw`
- **derived:**
  - `scale (mu/sigma)`
  - `ridge expected_rr + GNB p_win + Mahalanobis confidence`
  - `raw path (no F-044 gate bypass theatre)`
- **outputs:**
  - `expected_rr_raw`
  - `p_win_raw`
  - `ml_score_raw`
  - `confidence_raw`
  - `d_sq`
- **note:** `OFF-spine; rr_fusion.enabled=false`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\rr_trained\XAUUSD\20260728T063056Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.520440828780916, "mean": 0.4943601648415651, "min": 0.4837924671716808, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.493818432103816, "std": 0.006141481804036539}}`
- **sample native (first ok bar):**
```json
{
  "confidence_raw": 3.6001289965651305e-44,
  "d_sq": 200.06554882907741,
  "dof": 27,
  "expected_rr_raw": -0.06660092146935269,
  "ml_score_raw": 0.4944501511476146,
  "n_features": 38,
  "p_win_raw": 3.4589907533719982e-43,
  "score": 0.4944501511476146,
  "semantic": "rr_trained_nano_inference_raw"
}
```
- **config keys read:** ['engine_runner.rr_fusion.enabled', 'engine_runner.rr_fusion.model_path']

## Model: `strategies`

- **Status:** BLOCKED
- **Entry:** `strategies.strategy_orchestrator.StrategyOrchestrator`
- **Spine active:** False
- **Audit tag:** DEPRECATED
- **Description:** S1-S10 sidecar; not on live spine

### Feature flow

- **inputs:** `strategy-specific`
- **outputs:**
  - `consensus score`

**Blocked:** Sidecar S1-S10; participates_in_live_spine=false

## Model: `tradenet`

- **Status:** OK
- **Entry:** `training.trade_net_v2.TradeNetV2.predict`
- **Spine active:** False
- **Audit tag:** UNWIRED
- **Description:** TradeNet v2 multi-head (requires --artifact)

### Feature flow

- **inputs:** `full canonical feature dict → 39-vector (name-anchored)`
- **derived:**
  - `optional scaler`
  - `MLP trunk 39→32→16`
  - `3 sigmoid heads: p_tp1, p_tp2, p_survives_be`
  - `composite = 0.4*p_tp1 + 0.4*p_tp2 + 0.2*p_survives_be`
- **outputs:**
  - `tradenet_score`
  - `p_tp1`
  - `p_tp2`
  - `p_survives_be`
- **note:** `UNWIRED F-005; XAUUSD v2 envelope degenerate metrics`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\tradenet\XAUUSD\20260728T063118Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.5022698044037004, "mean": 0.23441158115768382, "min": 0.04774495589783759, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.22289779319825673, "std": 0.12417189771594117}}`
- **sample native (first ok bar):**
```json
{
  "p_survives_be": 0.26475142738313406,
  "p_tp1": 0.0013362774017074068,
  "p_tp2": 5.988265361149192e-39,
  "schema_version": "tradenet_v2",
  "score": 0.05348479643730978,
  "tradenet_score": 0.05348479643730978
}
```

## Model: `zone_gate`

- **Status:** OK
- **Entry:** `engines.zone_cluster_score.score_zone_cluster`
- **Spine active:** True
- **Audit tag:** REDUNDANT
- **Description:** Production zone cluster score (hard path)

### Feature flow

- **inputs:** `full CANONICAL_FEATURES (39) name-anchored vector`
- **derived:**
  - `BitNetZoneGate.check(vector) → top_scores`
  - `cluster_score if len(top_scores) >= cluster_min_n else best`
  - `passed = score >= zone_cluster_threshold`
- **outputs:**
  - `score`
  - `passed`
  - `best_zone_id`
  - `top_scores`
  - `cluster_score`
- **config_keys:**
  - `engine_runner.zone_registry_path`
  - `engine_runner.zone_cluster_threshold`
  - `engine_runner.zone_gate.{top_k,cluster_min_n,cluster_spread_max}`

### Run capture

- **run_dir:** `D:\Tradelatest\results\model_runners\zone_gate\XAUUSD\20260728T063139Z`
- **n_ok / n_error:** 200 / 0
- **summary:** `{"n_bars": 200, "n_error": 0, "n_ok": 200, "score_stats": {"max": 0.8814343099873523, "mean": 0.7446011934248634, "min": 0.5588251488626041, "n": 200, "n_finite": 200, "n_non_finite": 0, "p50": 0.7513913721377672, "std": 0.07283190173721996}}`
- **sample native (first ok bar):**
```json
{
  "best_zone_id": "zone_2",
  "best_zone_score": 0.7259,
  "cluster_score": 0.6992515509155328,
  "meta": {
    "passed": true,
    "score": 0.6992515509155328,
    "valid": true,
    "vector": [
      2389.44,
      2390.07,
      2386.79,
      2387.55,
      1935.0,
      0.6250807597880863,
      1.0,
      2391.158935546875,
      2395.874755859375,
      -2230.502197265625,
      -1.0,
      -1.7265390869110795,
      -931.7762451171875,
      0.0021142414771020412,
      0.6497806310653687,
      38.629518051927455,
      -5.449422536913062,
      -5.617049723324211,
      0.6037609909490453,
      0.0,
      0.0,
      -1.0,
      0.0,
      0.0,
      0.0,
      1.0,
      1.8899999999998727,
      3.2800000000002,
      0.5762194991111755,
      2.0,
      2.0,
      20.0,
      0.3744162917137146,
      0.714944064617157,
      1.0,
      0.3843214809894562,
      0.8251742124557495,
      0.0
    ]
  },
  "passed": true,
  "score": 0.6992515509155328,
  "top_scores": [
    0.7258856886897646,
    0.7050595186646083,
    0.6639661649688117
  ],
  "valid": true,
  "vector": [
    2389.44,
    2390.07,
    2386.79,
    2387.55,
    1935.0,
    0.6250807597880863,
    1.0,
    2391.158935546875,
    2395.874755859375,
    -2230.502197265625,
    -1.0,
    -1.7265390869110795,
    -931.7762451171875,
    0.0021142414771020412,
    0.6497806310653687,
    38.629518051927455,
    -5.449422536913062,
    -5.617049723324211,
    0.6037609909490453,
    0.0,
    0.0,
    -1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    1.8899999999998727,
    3.2800000000002,
    0.5762194991111755,
    2.0,
    2.0,
    20.0,
    0.3744162917137146,
    0.714944064617157,
    1.0,
    0.3843214809894562,
    0.8251742124557495,
    0.0
  ],
  "vector_len": 38
}
```
- **config keys read:** ['engine_runner.zone_registry_path', 'engine_runner.zone_min_samples', 'engine_runner.zone_cluster_threshold', 'engine_runner.zone_gate_execution_mode', 'engine_runner.zone_gate', 'engine_runner.zone_gate.top_k', 'engine_runner.zone_gate.cluster_min_n', 'engine_runner.zone_gate.cluster_spread_max']

## Authority & non-claims

- No economic edge claim from these scores.
- No production config or model registry mutation.
- Fusion compose ≠ full EngineRunner decision path.
- BitNet/TradeNet/rr_trained runs do **not** enable those systems in production.

Machine summary: `D:/Tradelatest/results/model_runners/XAUUSD/ALL_MODELS_SUMMARY.json`
