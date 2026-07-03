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
    volume:    float = 0.0
    index:     int   = 0   # candle position in the source series; [PATCH 4] time-based rules

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

**`TradePathStats`** (Metrics Layer V2 — Layer A; on `TradeRecord.path`). Raw within-trade path
observations tracked once per bar (strictly after entry, incl. the exit bar) by
`TradeJournal.observe_open_bar`, deliberately identical to `research.measurement.forward_walk`
(the verifying oracle). Observation-only — never feeds the exit decision.

```python
@dataclass
class TradePathStats:
    mfe_price: float; mae_price: float           # entry_raw-relative excursion (>=0 / <=0)
    bars_to_peak: int; bars_to_trough: int; bars_observed: int
    mfe_rr: float; mae_rr: float                 # derived at close (raw risk basis)
    capture_ratio: float|None                    # realized_raw / mfe   (None if mfe<=0)
    giveback: float|None                         # (mfe-realized_raw)/mfe
    time_efficiency: float|None                  # bars_to_peak / duration
    adverse_efficiency: float|None               # |mae_rr| / mfe_rr
```

**`BacktestMetrics.distribution["metrics_v2"]`** (Layer B aggregate; additive telemetry, mirrors
the ROI block). Independently recomputed by `analytics/metrics_oracle.py` for parity:

```python
{
  "rr":            {avg_realized_rr, avg_planned_rr, median_rr, rr_p10, rr_p50, rr_p90},
  "concentration": {largest_winner_rr, largest_loser_rr, top5_win_contribution_pct},
  "distribution":  {trades_per_week, trades_per_month, trades_per_session: {sess: n}, median_duration},
  "survival":      {median_capture_ratio, median_giveback, median_bars_to_peak,
                    mfe_rr_p50, mfe_rr_p90, mae_rr_p50, mae_rr_p90},
  "efficiency":    {median_time_efficiency, time_efficiency_p90, median_adverse_efficiency},
}
```

Multi-instrument `aggregate_summary.json` additionally carries `trades_per_symbol` and
`symbol_attribution` (per-symbol expectancy / PF / avg_rr / drawdown / trades_pct). Independently
recomputed by `analytics/metrics_oracle.py` (Oracle V2 + V3: efficiency / symbol-attribution /
concentration) for the parity gate.

### 2.2b Interpreter Contract — `src/interpreters/contract.py` (Schema 1.0)

An **Interpreter** is an event/feature producer (Level 4), distinct from a research `Hypothesis`
(trade emitter). Measured by bridging to a `Hypothesis` via `adapter.InterpreterHypothesis` →
`forward_walk` + `QualificationGate` (reused oracle; no new oracle). Pure / deterministic /
no-lookahead / identity-blind; `meta` opaque (forbidden for decisions); `explain()` telemetry-only.

```python
class EventKind(Enum):  # drift guard; extended per real interpreter (+a test)
    BREAKOUT; REVERSAL; SPRING; CATAPULT; OBSERVATION
    DOUBLE_TOP_BREAKOUT; DOUBLE_BOTTOM_BREAKDOWN   # Plan 5 — P&F (PNF-v1)

@dataclass(frozen=True)
class InterpreterEvent:
    kind: EventKind; confidence: float; strength: float   # confidence=how sure, strength=how powerful
    direction: Optional[Direction] = None                 # reuse frozen Direction; None = non-directional
    entry/sl_atr_mult/tp_atr_mult/atr: Optional[float]    # geometry → adapter Signal (directional only)
    meta: Mapping[str, Any]                               # OPAQUE telemetry; never a decision input

@dataclass(frozen=True)
class InterpreterReading:
    events: list[InterpreterEvent]; confidence: float
    trace_id: str                       # {NAME}-v{version}-{YYYYMMDD-HHMMSS} (deterministic)
    observation_time: datetime          # window's last bar ts (never wall-clock)
    schema_version: str = "1.0"; unknowns: list[str] = []; failure_conditions: dict = {}

@runtime_checkable class Interpreter(Protocol):  # name/family/economic_rationale + observe()+explain()
class BaseInterpreter:  # subclass _observe()->(events,confidence); base validates + stamps provenance
```

`InterpreterHypothesis(interp)` (adapter) implements `Hypothesis.detect()` — directional events →
`Signal`s (provenance in `Signal.meta`). Identity-blind: detect() reads only events.

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

### 4.1 Canonical 38-dim vector — `src/features/feature_schema.py`

> Schema v3.0 = **38** features (the v2.0 core 35 at indices 0–34, preserved unchanged, plus three
> v3.0 additions at indices 35–37). `SCHEMA_V2_FEATURE_DIM = 35` is the backward-compat sentinel
> that models storing 35 features slice to. `feature_schema.py` is authoritative.

```python
CANONICAL_FEATURE_DIM = 38   # == len(CANONICAL_FEATURES); hard-asserted at import

CANONICAL_FEATURES: tuple[str, ...] = (
    # ── indices 0–34 (v2.0, preserved unchanged) ─────────────────
    "open", "high", "low", "close", "volume",
    "volume_ratio",
    "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength",
    "momentum_score",
    "atr", "volatility_ratio",
    "rsi_14",
    "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size", "wick_size", "body_ratio",
    "volatility_regime",
    "session", "hour_of_day",
    "disp_strength", "retest_depth", "candles_since_retest",
    # ── indices 35–37 (v3.0, NEW) ────────────────────────────────
    "liquidity_distance", "liquidity_pressure_score", "volume_spike",
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
        "expectancy_rr":   0.5,
        "win_rate":        0.2,
        "trade_count_norm": 0.2,
        "drawdown":        0.1
    }
}
```

### 5.2 GoalSpec / GoalReport — Goal Layer (economic objective)

`GoalSpec` (`src/config_layer/goal_schema.py`) is the frozen, machine-readable economic
objective loaded from the `goal` config section (id **G001**). `GoalReport`
(`src/config_layer/goal_validator.py`) is the comparison of measured metrics against it,
emitted as additive telemetry at `BacktestMetrics.distribution["goal_report"]`.

```python
GoalSpec = {                                    # frozen dataclass; all targets Optional
    "enabled":  bool,                           # False ⇒ advisory no-op (no/absent section)
    "goal_id":  str,                            # "G001"
    "enforce":  bool,                           # DORMANT (default False)
    "trades_per_month_min/target/max": float | None,
    "avg_rr_min": float | None, "win_rate_min": float | None,
    "max_drawdown_pct_max": float | None, "expectancy_r_min": float | None,
    # + risk_per_trade_target, timeframe_*, instruments, reaction_only/human_execution/no_prediction
}

GoalReport = {                                  # → distribution["goal_report"]
    "enabled":  bool,
    "enforced": bool,                           # mirrors GoalSpec.enforce
    "goal_id":  str,
    "decision": "PASS" | "FAIL",                # disabled or all-SKIP ⇒ PASS
    "criteria": [                               # one row per declared bound
        {"name": str, "comparator": ">=" | "<=", "target": float,
         "actual": float | None, "gap": float | None,   # gap>0 ⇒ satisfied w/ margin
         "status": "PASS" | "FAIL" | "SKIP"},   # SKIP ⇒ metric not supplied (never fails)
    ],
}
```

Authority: advisory-only in the backtest hot path (measure-only). Promotion HARD-blocks on a
FAIL **only when** `goal.enforce=True` — `config_validator._run_quality_gates` folds the failed
criteria into `ValidationReport.hard_failures`.

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
    "goal":               dict,                 # G001 economic-objective targets (Goal Layer)
    "agent":              dict,                 # BitNet 3B, REPL, copilot_auto_narrate
    "validation_summary": dict,                 # metrics from the approving ValidationReport
}
```

---

## 9. JSONL Audit Line Schemas

Every JSONL line is self-contained. The `timestamp` + `kind` rule applies to **audit/event
streams** (§9.1–9.4); **registry-class** JSONL (§9.5–9.6 and `data/framework_registry.jsonl`,
see `framework_registry_schema.md`) carries `created` / `last_validated` (or a static meta
line) instead — registries are id-keyed truth projections, not time-ordered event logs.

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

### 9.4 Event-fabric streams (uniform envelope)

Cross-component telemetry uses one canonical envelope (`make_event_envelope`,
`src/events/event_fabric.py:119`); `payload` is event-specific:

```python
EventEnvelope = {
    "event_id":        str,     # 8-char hex UUID fragment — correlation
    "generation":      int,     # monotonic per-process counter — ordering within session
    "event_type":      str,     # EventType member (src/events/event_fabric.py:56)
    "instrument":      str,     # "" for system-level events
    "source":          str,     # originating component ("CRTEngine", "CognitiveBus", …)
    "timestamp":       str,     # ISO-8601 UTC
    "schema_hash":     str,     # FEATURE_ORDER_HASH at emission — passive drift detector
    "parent_event_id": str,     # causal chain ("" = root)
    "payload":         dict,
}
```

Stream directory (`EventType` → file → emitter; the per-model consumers are indexed in
`active_models.yaml` `reachability.telemetry`):

| EventType | Stream | Emitter |
|---|---|---|
| `ENGINE_TELEMETRY` | `logs/engine_telemetry.jsonl` | `src/utils/engine_telemetry.py` |
| `DECISION_LINEAGE` | `logs/decision_lineage.jsonl` | `src/utils/engine_telemetry.py` |
| `DRIFT_AUDIT` | `logs/drift_audit.jsonl` | `src/replay/replay_drift_governor.py` |
| `TRADE_LIFECYCLE` | `logs/trade_lifecycle.jsonl` | `src/utils/trade_logger.py` |
| `STATE_TRANSITION` | `logs/crt_transitions.jsonl` | `src/config_layer/crt_engine_v2.py` |
| `LLM_TURN` | `multi_llm/turn_ledger.jsonl` | `src/multi_llm/turn_ledger.py` |

### 9.5 `data/findings.jsonl` (GENERATED — never hand-edit)

Machine-readable derived view of `docs/current-findings.md` (the authoritative store, §6.2).
Regenerate: `python scripts/governance/export_findings.py`. Generator:
`src/governance/findings_export.py`; guard: `tests/test_findings_export.py` (determinism +
hand-edit detection). Line 0 is a static meta record (`kind: "meta"`, `schema:
"findings_export/1"`, `source`, `generated_by` — no timestamp, so reruns are byte-identical);
then one line per finding in doc order:

```python
FindingLine = {
    "kind":           "finding",
    "id":             str,          # F-NNN
    "title":          str,          # header text after "F-NNN · "
    "type":           str,          # ARCHITECTURE | ECONOMIC | GOVERNANCE | OPERATIONAL | RISK
    "status":         str,          # VALIDATED | OPEN | DURABLE | SUPERSEDED | RETIRED
    "confidence":     str,          # Certain | Likely | Possible
    "validated":      str,          # YYYY-MM-DD
    "revalidate_by":  str | None,
    "evidence":       str | None,   # verbatim from the doc
    "evidence_paths": list[str],    # committed docs/src/tests/scripts paths cited in the block
    "supersedes":     str | None,
    "superseded_by":  str | None,
    "reversal":       str | None,
    "owner":          str | None,
    "note":           str | None,
    "terminal":       bool,         # SUPERSEDED/RETIRED status or ## Terminal section
}
```

### 9.6 `data/hypothesis_registry.jsonl` (seeded — edit the seed, not the file)

Research-hypothesis registry (H-ids ↔ findings ↔ models). Committed truth =
`scripts/governance/seed_hypothesis_registry.py` (the framework-registry precedent); the JSONL
is its deterministic projection. Module: `src/governance/hypothesis_registry.py`; guard:
`tests/test_hypothesis_registry.py`; query/CI gate:
`python scripts/governance/query_hypotheses.py --validate`.

```python
HypothesisLine = {
    "id":              str,          # H-NNN
    "statement":       str,          # one falsifiable sentence
    "family":          str | None,   # aligns with research Hypothesis.family where a code twin exists
    "status":          str,          # open | validated | falsified | frozen | superseded
    "authority":       "research",   # PINNED — the registry can never grant more (§6.5)
    "findings":        list[str],    # F-ids; must resolve in docs/current-findings.md
    "models":          list[str],    # top-level active_models.yaml keys (minus meta/philosophy)
    "code_hypotheses": list[str],    # names registered in research HYPOTHESIS_REGISTRY (may be [])
    "programs":        list[str],    # pre-registration doc paths
    "evidence":        list[dict],   # {path, line, symbol, type} — framework-registry evidence shape
    "created":         str,          # pinned ISO-8601 (byte-stable reruns)
    "last_validated":  str,
    "notes":           str,
}
```

**Authority note (§6.5).** `status: validated` is a *research* verdict only. The registry
defines **no** promotion thresholds; the only promotion path remains the M4
`QualificationGate` (`src/research/qualification.py`) → `ConfigValidator` →
`PromotionManager`. Enforced by a negative-guard test (no `promotion_requirements` /
`min_delta*` / threshold keys can enter the schema).

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
      EngineRunner  FusionEngine  ExecPlanner   UltronRiskGate  llm_inference_client

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
