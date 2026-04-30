# SCHEMAS.md

> Canonical data shapes of the Tradelatest codebase.
> This is **not** an ORM schema — there is no database. Shapes live in Python
> dataclasses, enums, JSON configs, and JSONL audit lines.

---

## 1. "Model" Inventory (no DB — all in-memory + JSON)

The codebase has **no SQL models and no ORM**. Persisted state falls into three categories:

| Storage                                                             | Shape                                 | Persistence              |
| ------------------------------------------------------------------- | ------------------------------------- | ------------------------ |
| `configs/production/*.json`                                         | Versioned config (section-per-key)    | Immutable once promoted  |
| `configs/promotion_log.jsonl`, `logs/*.jsonl`                       | Append-only event lines               | Immutable, ordered       |
| `results/tuner/*.json`, `results/validation/{approved,rejected}/*.json` | Artifacts keyed by SHA-256 or label | Regenerable              |
| In-memory: `core/feature_store.py`, `FeatureMonitor` window=500     | Rolling buffers                       | Process-lifetime only    |
| `models/zone_registry.json`, `models/rr_model.json`                 | Model-metadata JSON                   | Atomic-replace (GOV-3)   |

---

## 2. Core Dataclasses

### 2.1 Market primitives — `src/config_layer/crt_engine_v2.py`

```python
@dataclass
class Candle:
    timestamp: datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    index:     int         # position in the source series

@dataclass
class Range:
    low:         float
    high:        float
    expansion:   float     # expansion multiplier vs. ATR
    age_candles: int

@dataclass
class Trade:
    entry:     float
    exit:      float
    sl:        float
    tp:        float
    direction: "Direction"
    rr_ratio:  float
```

### 2.2 Backtest configuration — `src/runtime/backtest_v2.py`

```python
@dataclass
class BacktestConfig:
    retest_depth_max:             float
    retest_atr_depth_fraction:    float
    body_ratio_min:               float
    atr_multiplier_min:           float
    expansion_atr_min_distance:   float
    # ... additional config-driven fields consumed by BacktestRunner

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "BacktestConfig":
        """Factory — every field reads from configs/production/*.json."""
```

### 2.3 Control plane — `src/control_plane/types.py`

```python
@dataclass
class CommandSpec:
    name:        str
    description: str
    category:    str             # e.g. "training" | "backtest" | "promotion"
    argv:        list[str]       # command template with {placeholder} tokens
    params:      list[dict]      # [{name, type, default, required}]

@dataclass
class RunRecord:
    run_id:       str
    command_name: str
    status:       str            # "pending" | "running" | "succeeded" | "failed"
    started_at:   datetime
    finished_at:  datetime | None
    argv:         list[str]
    exit_code:    int | None
    log_path:     str
    artifacts:    list[str]
```

### 2.4 Agent — `src/agent/state.py`, `src/agent/plan_compiler.py`

```python
@dataclass
class ToolStep:
    tool_name: str
    args:      dict              # may contain {placeholder} tokens resolved by ArgFiller
    required:  bool = True

@dataclass
class Plan:
    intent_key: str
    steps:      list[ToolStep]

@dataclass
class AgentState:
    session_id:      str
    messages:        list[dict]      # [{role, content}]
    last_intent:     str | None
    last_outcome:    dict | None     # {success: bool, metrics: dict, error: str | None}
```

---

## 3. Enums

### 3.1 CRT state machine — `src/config_layer/crt_engine_v2.py`

```python
class CRTState(Enum):
    RANGE         = "RANGE"
    SWEEP         = "SWEEP"
    DISPLACEMENT  = "DISPLACEMENT"
    EXPANSION     = "EXPANSION"
    RETEST        = "RETEST"
    EXECUTION     = "EXECUTION"
    RESOLUTION    = "RESOLUTION"

class Direction(Enum):
    LONG  = "LONG"
    SHORT = "SHORT"
    NONE  = "NONE"

class RejectReason(Enum):
    LOW_SCORE        = "LOW_SCORE"
    OUTSIDE_SESSION  = "OUTSIDE_SESSION"
    NO_DOUBLE_SWEEP  = "NO_DOUBLE_SWEEP"
    NEWS_FILTER      = "NEWS_FILTER"
    HIGH_SPREAD      = "HIGH_SPREAD"
    INVALID_STATE    = "INVALID_STATE"
```

### 3.2 Intent (agent + execution planner)

```python
# Defined contextually per config; canonical set used by ExecutionPlannerV1_2:
INTENT = Literal["BREAKOUT", "PULLBACK", "REVERSAL", "LIQ_SWEEP"]
```

### 3.3 Engine completeness — `src/core/engine_runner.py`

```python
EXPECTED_ENGINES: set[str] = {"crt", "gaussian", "zone_gate", "rr"}
```

---

## 4. Feature Schema

### 4.1 Canonical 35-dim vector — `src/features/feature_schema.py`

```python
CANONICAL_FEATURE_DIM = 35

CANONICAL_FEATURES: tuple[str, ...] = (
    # OHLCV primitives
    "open", "high", "low", "close", "volume",
    # Volatility + momentum
    "atr", "atr_ratio", "adx", "rsi", "momentum",
    # CRT-specific
    "expansion_score", "retest_depth", "body_ratio",
    "disp_strength", "candles_since_retest",
    # Session + regime
    "session_id", "regime_id",
    # ... 18 additional features — see feature_schema.py for the full canonical tuple
)

FEATURE_SCHEMA: dict[str, type]   # name → type (float | int | str | bool | dict)
```

Changes to `CANONICAL_FEATURES` or `FEATURE_SCHEMA` **break backward compatibility** — baseline must be re-captured.

### 4.2 SchemaObject wrapper

```python
class SchemaObject:
    """Dict-like container with attribute access used by feature builders."""
    __getitem__ / __setitem__ / __getattr__
```

---

## 5. ValidationReport (primary decision DTO)

Produced by `ConfigValidator.validate()` — this is the only object that unlocks promotion.

```python
ValidationReport = {
    # ── Top-level outcome ─────────────────────────────────────────
    "decision":           Literal["APPROVE", "REJECT"],
    "config_id":          str,
    "validated_at":       str,                  # ISO-8601 UTC
    "params":             dict,                 # input params echoed

    # ── Aggregate metrics ─────────────────────────────────────────
    "metrics": {
        "final_score":          float,
        "mean_score":           float,
        "consistency_penalty":  float,          # penalty for cross-instrument variance
        "total_trades":         int,
        "max_drawdown":         float,          # percent, e.g. 22.5
    },

    # ── Per-instrument breakdown ──────────────────────────────────
    "per_instrument": {
        "EURUSD": {
            "score":          float,
            "trades":         int,
            "win_rate":       float,            # 0.0 – 1.0
            "expectancy_rr":  float,            # R-multiples per trade
            "max_drawdown":   float,
            "total_pnl_rr":   float,
            "error":          str | None,
        },
        # ... one entry per CSV passed in
    },

    "instruments_tested": list[str],

    # ── Gates ─────────────────────────────────────────────────────
    "hard_failures": list[str],                 # e.g. "min_trades", "max_drawdown", "min_fitness"
    "warnings":      list[str],                 # soft-gate messages
}
```

### 5.1 Hard + Soft gate thresholds (read from config)

```python
# From configs/production/v1_multi_2026_03.json → "config_validator":
{
    "min_trades_per_instrument": 10,            # HARD
    "max_drawdown_pct":          35.0,          # HARD
    "score_threshold":           0.15,          # HARD (min fitness)
    "min_win_rate":              0.35,          # SOFT
    "min_expectancy":           -0.5,           # SOFT (R multiples)
    "max_score_std_dev":         0.2,           # SOFT (cross-instrument consistency)
    "trade_count_target":        100,
    "fitness_weights": {
        "expectancy":   0.35,
        "win_rate":     0.20,
        "trade_count":  0.20,
        "drawdown":     0.15,
        "consistency":  0.10
    }
}
```

---

## 6. GateResult — `UltronRiskGate.evaluate()` return shape

```python
GateResult = {
    "approved":             bool,
    "final_position_size":  float,              # lots / units
    "rejection_reason":     str | None,         # one of the rejection categories below
    "checks": {
        "ttl_expired":          bool,
        "rr_floor":             bool,
        "daily_trade_limit":    bool,
        "kill_switch":          bool,           # daily-loss breach
        "portfolio_exposure":   bool,
        "sl_distance":          bool,
    },
    "evaluated_at":         str,                # ISO-8601
}
```

---

## 7. ExecutionPlan — `ExecutionPlannerV1_2.plan()` return shape

```python
ExecutionPlan = {
    "execution_id":        str,                 # deterministic per (signal_id, candle_ts)
    "entry":               float,
    "sl":                  float,
    "tp":                  float,
    "rr_ratio":            float,
    "position_size_hint":  float,               # pre-risk-gate sizing hint
    "ttl_seconds":         int,                 # intent-specific
    "intent":              Literal["BREAKOUT","PULLBACK","REVERSAL","LIQ_SWEEP"],
}
```

Per-intent multipliers are read from `configs/production/*.json → execution_planner`:

```python
{
    "BREAKOUT":   {"tp_atr_mult": 2.5, "ttl_seconds": 1800, "default_sl_atr_mult": 1.0},
    "PULLBACK":   {"tp_atr_mult": 2.0, "ttl_seconds": 3600, "default_sl_atr_mult": 1.2},
    "REVERSAL":   {"tp_atr_mult": 3.0, "ttl_seconds": 2400, "default_sl_atr_mult": 1.5},
    "LIQ_SWEEP":  {"tp_atr_mult": 2.0, "ttl_seconds": 900,  "default_sl_atr_mult": 0.8},
}
```
(Exact values live in the active production config — do not hard-code.)

---

## 8. Production Config JSON (top-level shape)

```python
ProductionConfig = {
    "version":            str,                  # e.g. "v1_multi_2026_03"
    "created_at":         str,                  # ISO-8601
    "config_hash":        str,                  # SHA-256 of canonicalised JSON (minus this field)

    "params":             dict,                 # CRT tunable parameters → CRTConfig
    "engine_runner":      dict,                 # model_path, sessions, thresholds, flags
    "execution_planner":  dict,                 # per-intent multipliers + defaults
    "ultron_risk_gate":   dict,                 # sizing, daily limits, kill-switch thresholds
    "fusion_engine":      dict,                 # weight_crt/gaussian/zone_gate/rr, normalizer
    "decision_engine":    dict,                 # fusion_min_score, per-regime thresholds
    "crt_engine":         dict,                 # CRT state-machine parameters
    "governance":         dict,                 # shadow_promotion config
    "llama_gate":         dict,                 # server_url, timeouts, fail_count_disable
    "config_validator":   dict,                 # hard + soft gate thresholds, fitness weights
    "agent":              dict,                 # BitNet 3B, REPL, copilot_auto_narrate
    "validation_summary": dict,                 # metrics from the approving ValidationReport
}
```

---

## 9. JSONL Audit Line Schemas

Every JSONL line is self-contained and must include `timestamp` + `kind`.

### 9.1 `configs/promotion_log.jsonl`

```python
PromotionLogLine = {
    "timestamp":        str,                    # ISO-8601 UTC
    "kind":             Literal["PROMOTE", "REJECT", "ROLLBACK"],
    "new_version":      str,
    "previous_version": str,
    "config_hash":      str,                    # SHA-256
    "report_id":        str,                    # ValidationReport id
    "score_std_dev":    float,
    "approver":         str,                    # user or "auto"
    "notes":            str | None,
}
```

### 9.2 `logs/agent_audit.jsonl`

```python
AgentAuditLine = {
    "timestamp":    str,
    "session_id":   str,
    "turn_id":      int,
    "intent":       str,
    "plan":         list[str],                  # resolved tool names
    "tool_call":    {"name": str, "args": dict},
    "outcome":      {"success": bool, "metrics": dict, "error": str | None},
}
```

### 9.3 `logs/expansion_trace.jsonl` / `expansion_rejected.jsonl`

```python
ExpansionLogLine = {
    "timestamp":      str,
    "kind":           Literal["STEP", "ACCEPT", "REJECT"],
    "base_version":   str,
    "param":          str,
    "from_value":     float,
    "to_value":       float,
    "score_before":   float,
    "score_after":    float,
    "reason":         str,                      # bounds | regression | hard_gate | accepted
}
```

---

## 10. Relationships

No foreign keys (no DB) — relationships are **directional references by ID / path**:

```
ValidationReport ─(report_id)─▶ PromotionLogLine
                                      │
                                      ▼
                          configs/production/{version}.json
                                      │
                                      ▼
               loaded by every consumer via get_prod_section(name)
                                      │
            ┌─────────────┬───────────┼───────────────┬──────────────┐
            ▼             ▼           ▼               ▼              ▼
      EngineRunner  FusionEngine  ExecPlanner   UltronRiskGate  llama_gate

checkpoint_multi.json ──(params)──▶ ConfigValidator.validate()
                                        │
                                        ▼
                                ValidationReport

AgentState ─(session_id)─▶ agent_audit.jsonl, intent_log.jsonl

CRTState transitions  RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION
(enforced in crt_engine_v2.py; no other state transitions are legal)

EngineRunner produces engine_results {crt, gaussian, zone_gate, rr}
  └─▶ FusionEngine.evaluate(engine_scores) → final_score ∈ [0, 1]
        └─▶ DecisionEngine → ACCEPT / REJECT
              └─▶ (on ACCEPT) ExecutionPlannerV1_2.plan() → ExecutionPlan
                    └─▶ UltronRiskGate.evaluate() → GateResult
```

---

## 11. Validation Rules

No Pydantic, no Zod, no class-validator. Validation is enforced by:

| Rule                                                           | Enforced at                                            | Mechanism                            |
| -------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------ |
| Required config keys present                                   | Module import                                          | `_require_key(cfg, name)` → `KeyError` |
| Config hash integrity                                          | Config load                                            | SHA-256 compare against `config_hash` field |
| Dataset min samples / entropy / class balance                  | `src/features/dataset_validator.py`                    | Hard thresholds with raised `ValueError` |
| Expansion parameter bounds                                     | `src/expansion/policy_schema.py` → `PARAM_BOUNDS`      | Reject mutation if out of bounds     |
| Engine completeness                                            | `core/engine_runner.py`                                | `EXPECTED_ENGINES` set equality      |
| Feature schema consistency                                     | `src/features/schema_validator.py`                     | Hash check against baseline          |
| Promotion preconditions                                        | `governance/promotion_manager.py`                      | `report["decision"] == "APPROVE"` + hash verify |
| Backtest warmup / data sufficiency                             | `runtime/backtest_v2.py`                               | `warmup_candles` parameter, raises if insufficient |
| TTL / RR / kill-switch thresholds                              | `core/ultron_risk_gate.py`                             | Hard checks in `evaluate()`          |
