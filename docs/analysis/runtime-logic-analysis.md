# CRT System Runtime & Logic Layer Analysis
> Standardised module documentation generated 2026-04-22
> Strictly following CODEBASE_ANALYSIS.md schema and tone

---

## Strategy Core Layer

---

### Module: `src/engines/scoring_engine.py`
✅ **Overview**: Canonical CRT deterministic scoring function. Implements the original mathematical signal model using 4 core structural features with exponential decay weighting. Pure functional implementation with zero side effects.

📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| `compute_scores()` | Primary CRT scoring function |
| Sweep Detector | Binary detection logic: 0.0 = no sweep / 0.7 = single sweep / 1.0 = double sweep |
| Breakout Scorer | Combined body ratio + displacement strength calculation |
| Retest Scorer | Gaussian kernel around optimal 0.5 retest depth |
| Time Decay | Exponential decay on candles since retest |
| Weighted Aggregator | Final weighted sum of all component scores |

🚧 **Quality Gates**:
- ✅ **All sub-scores bounded [0, 1]**
- ✅ **Fixed weighting ratios**: 35% Sweep / 25% Breakout / 20% Retest / 20% Time
- ✅ `disp_strength = move / atr` normalisation
- ✅ Hard fail on `atr == 0` → returns 0.0
- ✅ Retest distribution: `exp(-((retest_depth - 0.5)²) / 0.04)`
- ✅ Time decay constant λ = 0.05 per candle

🔗 **Integration Points**:
- Input: 7 feature values from feature pipeline
- Output: final score + individual component breakdown
- Called exclusively by `crt_engine.py`
- Consumed directly by FusionEngine as CRT engine input

⚠️ **Constraints**:
- All inputs must be normalised to [0,1] range
- Displacement strength capped at 2.0 × ATR
- No configurable parameters, all constants hardcoded
- Zero lookahead guarantee, no state maintained

🎯 **Operation**:
```python
result = compute_scores(
    body_ratio=0.72,
    move=0.0012,
    atr=0.0008,
    retest_depth=0.48,
    candles_since_retest=3,
    sweep_detected=True,
    double_sweep=False
)
# result["final"] = 0.0 → 1.0 signal strength
```

---

### Module: `src/engines/zone_gate_engine.py`
✅ **Overview**: BitNet Zone Gate with mixed failure strategy. Validates signals against precomputed historical zone registry using weighted nearest neighbour clustering. Implements fail-open on registry errors, fail-closed on schema errors.

📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Canonical Validator | Strict schema enforcement for input features |
| Registry Validator | Schema validation with fail-open behaviour |
| Cluster Scorer | Weighted nearest neighbour interpolation |
| Spread Filter | Rejects unstable clusters with high variance |
| Execution Mode Handler | Normal / force_pass operational modes |
| Session Counters | Module level execution statistics |

🚧 **Quality Gates**:
- ✅ **Cluster spread filter**: Reject if max-min > 0.15
- ✅ **Mixed failure strategy**: Schema errors block, registry errors pass neutral
- ✅ **Minimum 2 neighbours required** for cluster scoring
- ✅ All outputs clamped strictly to [0.0, 1.0]
- ✅ Default threshold = 0.5

🔗 **Integration Points**:
- Input: canonical feature dict + BitNet model function
- Output: score / passed / vector / valid flags
- Called from EngineRunner stage 3
- Soft score consumed directly by FusionEngine

⚠️ **Constraints**:
- Execution modes: normal / force_pass
- Counters reset on process restart
- Zone registry validation is optional
- 32-dimensional canonical vector required

🎯 **Operation**:
```python
result = run_zone_gate_engine(
    features,
    model_fn=bitnet_predict,
    threshold=0.5,
    zone_registry=registry,
    execution_mode="normal"
)
```

---

## Data Pipeline Layer

---

### Module: `src/features/feature_builder.py`
✅ **Overview**: Canonical feature vector builder with strict data integrity policy. No synthetic defaults, no silent fallbacks. Constructs the standard input dictionary required by all downstream engines.

📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Raw Field Validator | Mandatory OHLCV check |
| Derived Field Validator | Mandatory ATR / EMA / RSI check |
| Session Injector | "unknown" default for explicit rejection |
| Data Integrity Sentinel | Marks valid rows with `_data_integrity = "real"` |

🚧 **Quality Gates**:
- ✅ **NO DEFAULTS PERMITTED**: All required fields raise ValueError if missing
- ✅ 5 raw fields mandatory: close / high / low / open / volume
- ✅ 4 derived fields mandatory: atr / ema_fast / ema_slow / rsi
- ✅ `session = "unknown"` triggers adapter rejection
- ✅ Sentinel field only added when all validation passes

🔗 **Integration Points**:
- Input: raw tick / candle data
- Output: canonical feature dictionary
- Input to all scoring engines, fusion, BitNet
- Standardised interface across backtest / live

⚠️ **Constraints**:
- No indicator calculation performed internally
- All indicators must be pre-computed upstream
- Zero state, pure stateless operation
- No type coercion, strict type checking

🎯 **Operation**:
```python
builder = FeatureBuilder(config)
features = builder.build(raw_candle)
# features guaranteed complete or exception raised
```

---

## Signal Fusion & Decision Layer

---

### Module: `src/core/fusion_engine.py`
✅ **Overview**: Multi-engine weighted fusion system with dead engine detection, conflict resolution and score normalisation. The single source of truth for final signal aggregation.

📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| Engine Completeness Check | Validates all 4 engines return results |
| Health Tracker | Detects dead (always-zero) engines via rolling variance |
| Weighted Aggregator | Normalised weighted average of active engines |
| Conflict Resolver | Directional conflict detection and resolution |
| Score Normalizer | Rolling min-max normalisation over 1000 window |
| Convergence Controller | Optional stability penalty layer |

🚧 **Quality Gates**:
- ✅ **Official weighting ratios**:
  | Engine | Weight |
  |---|---|
  | CRT Deterministic | 30% |
  | Gaussian Scorer | 25% |
  | Zone Gate | 25% |
  | Risk/Reward Engine | 20% |
- ✅ Dead engines automatically excluded from weight sum
- ✅ Conservative conflict policy: reject on any directional disagreement
- ✅ Weights always normalise to sum = 1.0
- ✅ All scores clamped to [0, 1]

🔗 **Integration Points**:
- Input: engine results dict with crt / gaussian / zone_gate / rr
- Output: final_score, normalised_score, individual engine scores
- Called exclusively by EngineRunner stage 4
- Output feeds directly into DecisionEngine

⚠️ **Constraints**:
- Conflict resolution policies: conservative / majority
- All engine results required, no partial execution
- Dead engine detection window = 1000 samples
- Normalisation requires minimum 2 samples

🎯 **Operation**:
```python
fusion = FusionEngine(config=FusionConfig())
result = fusion.compute({
    "crt": crt_result,
    "gaussian": gaussian_result,
    "zone_gate": zone_result,
    "rr": rr_result
})
final_score = result["final_score"]
```

---

## Live Execution Layer

---

### Module: `src/engines/live_engine.py`
✅ **Overview**: Production live trading decision and alert system. Human-in-loop only, NO automatic order placement. Implements cooldown, deduplication, and tiered alerting logic.

📊 **Core Architecture**:
| Component | Purpose |
|---|---|
| BitNetZoneGate | Historical zone validation gate |
| Decision Engine | 4 tier decision ladder |
| Alert State Tracker | Per-symbol cooldown + duplicate setup filter |
| Telegram Formatter | Standardised actionable alert messages |
| Audit Logger | Immutable log of every decision (sent or suppressed) |
| Kill Switch | Global enable/disable via environment variable |

🚧 **Quality Gates**:
- ✅ **Decision ladder execution order**:
  1. `confidence < 0.55` → **BLOCK**
  2. `RR >= 1.5 AND confidence >= 0.60` → **EXECUTE**
  3. `RR >= 1.5 AND confidence < 0.60` → **WARN**
  4. `ML > 0.75` → **WATCH**
  5. Default → **BLOCK**
- ✅ 60 second per-symbol cooldown
- ✅ 4 candle duplicate setup filter
- ✅ ALL signals logged regardless of alert status

🔗 **Integration Points**:
- Input: raw trade setup + Gaussian model + scaler
- Output: Telegram alert + audit log entry
- Called from execution loop after pipeline completion
- Human remains final execution authority

⚠️ **Constraints**:
- Never places orders, never connects to broker API
- Telegram is the only notification channel
- Default state: disabled (dry run)
- Alert cooldown cannot be overridden

🎯 **Operation**:
```bash
# Environment configuration
export LIVE_ENGINE_ENABLED=1
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```
```python
engine = LiveEngine(LiveEngineConfig.from_env())
result = engine.process(trade_data, gaussian_model, scaler)
```

---

## 🔍 Data Lineage Map
```
Raw Market CSV
    ↓
prepare_data.py → OHLCV + timestamps
    ↓
unified_data_builder.py → indicator calculation
    ↓
feature_builder.py → canonical feature dict
    ↓
feature_dict_to_vector() → 32-dimensional float vector
    ↓
BitNet / Gaussian / CRT / Zone engines
    ↓
FusionEngine.compute() → weighted final score
    ↓
DecisionEngine → GO / NO-GO
    ↓
LiveEngine → human alert
```

---

## 🎯 Fusion Weighting Logic Reference

### Final Score Calculation
```math
\begin{align*}
W_{total} &= W_{crt} + W_{gaussian} + W_{zone} + W_{rr} \\
\\
Final\ Score &= \frac{
    (0.30 \times S_{crt}) +
    (0.25 \times S_{gaussian}) +
    (0.25 \times S_{zone}) +
    (0.20 \times S_{rr})
}{W_{total}}
\end{align*}
```

### Engine Health Rules
- Engine considered dead if `mean == 0.0 AND variance == 0.0` over rolling window
- Dead engine weight set to 0.0
- Remaining weights automatically renormalised
- Warning logged on first dead engine detection

---

## ✅ Analysis Completion Status

| Category | Status |
|---|---|
| Strategy Core | ✅ Fully Documented |
| Data Pipeline | ✅ Fully Documented |
| Signal Fusion | ✅ Fully Documented |
| Live Execution | ✅ Fully Documented |
| Data Lineage | ✅ Mapped |
| Weighting Logic | ✅ Extracted |

All requested modules have been analysed and documented following the exact schema and tone specified.