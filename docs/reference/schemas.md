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

### 4.1 Canonical 39-dim vector — `src/features/feature_schema.py`

> Schema v4.0 = **39** features. Corrected 2026-08-07 (was documented here as 38-dim/v3.0; code
> moved to 39-dim/v4.0 in F-062, 2026-07-31 — this table had drifted, not the code). `feature_schema.py`
> is authoritative; quote `CANONICAL_FEATURE_DIM` from the module, not a number from this doc.
> `SCHEMA_V2_FEATURE_DIM = 35` and `SCHEMA_V3_FEATURE_DIM = 38` remain as backward-compat sentinels
> for models storing an earlier layout.

```python
CANONICAL_FEATURE_DIM = 39   # == len(CANONICAL_FEATURES); hard-asserted at import

CANONICAL_FEATURES: tuple[str, ...] = (
    "open", "high", "low", "close", "volume",             # 0-4
    "volume_ratio",                                        # 5
    "double_sweep",                                         # 6
    "ema_fast", "ema_slow", "ema_spread",                  # 7-9
    "trend_bias", "trend_strength",                        # 10-11
    "momentum_score",                                       # 12
    "atr", "volatility_ratio",                             # 13-14
    "rsi_14",                                               # 15
    "macd_line", "macd_signal",                            # 16-17
    "macd_hist_raw", "macd_hist_z",                        # 18-19 (v4.0: split from v3.0 "macd_hist")
    "sweep_detected", "liquidity_sweep", "break_of_structure",  # 20-22
    "swing_high", "swing_low", "higher_high", "lower_low", # 23-26
    "body_size", "candle_range", "body_ratio",             # 27-29 (v4.0: "candle_range" renamed from v3.0 "wick_size")
    "volatility_regime",                                    # 30
    "session", "hour_of_day",                              # 31-32
    "disp_strength", "retest_depth", "candles_since_retest",  # 33-35
    "liquidity_distance", "liquidity_pressure_score", "volume_spike",  # 36-38
)

FEATURE_SCHEMA: dict[str, type]   # name → type (float | int | str | bool | dict)

# Read-side only — decodes historical v3.0 records; never emitted by new code:
SCHEMA_V3_ALIASES: dict[str, str] = {
    "wick_size": "candle_range",
    "macd_hist": "macd_hist_z",   # v3.0's single field was the z-scored value, not the raw diff
}
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
streams** (§9.1–9.4); **registry-class** JSONL (§9.5–9.8 and `data/framework_registry.jsonl`,
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

### 9.7 `configs/stack_epoch_log.jsonl` (Research Provenance Spine, Phase 0)

Append-only, same discipline as `configs/promotion_log.jsonl` (§9.1) — never rewrite a line.
Module: `src/config_layer/stack_version.py` (`compute_stack_version()` / `resolve_epoch()` /
`append_epoch_record()`). Read-only; `authority: "NONE"` on every line — a `stack_epoch`
changing is a fact about what ran, not permission to run it (§6.5).

Names one composite identity over the four authorities (WHAT `market_ontology.yaml` / HOW
`configs/production/*.json` / WHO `active_models.yaml` / EXECUTION `candle_math.py` +
`derived_math.py` + `feature_schema.py`), so a result can cite *which stack produced it*.
Two hashes, not one — `behavior_hash` covers only inputs that can move a trade ledger
(active formulas via the ontology's `frozen_runtime_keys`, the whole production config file,
schema/execution identity, and only *executing* model checkpoints per
`production_bundle.load_production_bundle().executing_families()`); `provenance_hash` adds
everything else worth auditing (all families regardless of execution status, full-file
ontology/WHO hashes, `ProductionBundle.divergences`). Editing a `notes:`/`taxonomy:` block or
swapping a disabled model's artifact moves `provenance_hash` only — `behavior_hash` stays
byte-identical, which is what makes it safe to cite from a finding.

```python
StackEpochLine = {
    "timestamp":            str,        # ISO-8601 UTC
    "kind":                 str,        # "STACK_EPOCH" | "STACK_PROVENANCE"
    "stack_epoch":          int,        # monotonic; increments ONLY on unseen behavior_hash
    "behavior_hash":        str,        # sha256 hex
    "provenance_hash":      str,        # sha256 hex
    "active_version":       str,        # configs/production/ACTIVE_VERSION at capture time
    "executing_families":   list[str],  # families with executes_checkpoint==True
    "divergences":          list[str],  # ProductionBundle.divergences, reported not resolved
    "authority":            "NONE",     # PINNED
}
```

A `STACK_EPOCH` line mints a new `stack_epoch` (previously-unseen `behavior_hash`); a
`STACK_PROVENANCE` line references the current epoch when only `provenance_hash` moved.
`src/runtime/baseline_capture.py` embeds the same two hashes in its `stack_version` manifest
block, and now resolves all 6 model families' artifact hashes through
`load_production_bundle()` rather than 3 hardcoded registry paths — this fixed a real bug
where it pinned `models/zone_registry.json` (the v3 rollback artifact) instead of the
config-declared `zone_registry_path` (`models/zone_registry_v4_2026_07.json`), and a second
where its `ROOT_DIR` (needed as `src/` for imports) was reused as the repo-root for file
paths, silently nulling `config_sha256` and the registry counts. Guard: `tests/test_stack_version.py`.

### 9.8 `data/script_registry.jsonl` (SITS — seeded; edit stubs/overlays, not the file)

Script & Implementation Traceability System inventory. **PRIMARY** truth is hybrid:

1. `docs/governance/script_registry_stubs.jsonl` — machine-owned bulk rows
   (`python scripts/analysis/script_census.py --write-stubs …`; path-stable SCR ids).
2. `scripts/governance/seed_script_registry.py` — curated **overlays** only (purpose /
   category / status refinements).

Generated projection: `data/script_registry.jsonl` (gitignored). Module:
`src/governance/script_registry.py`; guard: `tests/test_script_registry.py`; query:
`python scripts/governance/query_scripts.py --validate`. Design:
`docs/implementation_plan/script-implementation-traceability-sits-design.md`.

**Authority pinned:** `"authority": "inventory"` on every line — no promote / economic power
(§6.5). **Lifecycle** is the sole terminal axis (`SUPERSEDED` / `DEAD` / `ARCHIVED`);
`category` is role-only (no DEAD/SUPERSEDED categories).

```python
ScriptRecord = {
    "id":                     str,   # SCR-NNN (zero-padded; never reuse)
    "path":                   str,   # POSIX repo-relative
    "category":               str,   # PROBE|DIAGNOSTIC|RESEARCH_RUNNER|CANONICAL_CLI|
                                     # TRAINING|GOVERNANCE|DATA|MAINTENANCE|ORPHAN
    "lifecycle":              str,   # ACTIVE|EPHEMERAL|SUPERSEDED|DEAD|ARCHIVED
    "implementation_status":  str,   # LOGIC_IN_SCRIPT|EXTRACTED_TO_SRC|WIRED|REGISTERED|
                                     # TESTED|CLOSED_EPHEMERAL|N_A|ACCEPTED_COLOCATED
    "owner_kind":             str,   # HUMAN|AGENT|MIXED|UNKNOWN
    "owner_ref":              str,
    "purpose":                str,
    "task_refs":              list[str],
    "dest_modules":           list[str],
    "tests":                  list[str],
    "config_keys":            list[str],
    "control_plane_id":       str | None,
    "agent_tool_id":          None,  # reserved v1.1; non-null rejected in v1
    "has_main":               bool,
    "superseded_by":          str | None,  # required when lifecycle=SUPERSEDED
    "created":                str,   # ISO-8601 UTC
    "last_validated":         str,
    "ttl_days":               int | None,  # null until Phase-4 debt curation
    "logic_in_script":        bool,
    "notes":                  str,   # DEAD requires non-empty; valid plan: dest_modules or
                                     # wontfix:reason=…
    "authority":              "inventory",  # PINNED
}
```

PR-2 (Phase 1): full-universe stubs + grandfather pin + `script-matrix.md` + **path-coverage
assert on GREEN_FLOOR** (`tests/test_script_registry.py`, `tests/test_script_matrix_sync.py`).
PR-3 (Phase 2): **grandfather ratchet** — paths outside the pin need overlay classification
(`purpose ≠ GRANDFATHER_UNCLASSIFIED`); change class `SCRIPT_LIFECYCLE_CHANGE`; construction
completion fails if declared scripts omit the SITS floor.
PR-4 (Phase 3): **CANONICAL_CLI ↔ CommandSpec** — seed reverse-maps curated control-plane
scripts; parity floor + `script_canonical_allowlist.json` exceptions; no mass CommandSpec dump.
PR-5 (Phase 4): **TTL debt gate** — calendar age vs `ttl_days`; only curated TTLs bind CI;
`--missing-impl --jsonl` queue-shaped export; debt markdown via `--export-debt-report`.
PR-6 (optional extract): SITS cores under `src/governance/script_{registry,census,seed}.py`;
CLI wrappers thin; `implementation_status` TESTED/WIRED; spine non-import floor.
Empty registry is only valid for offline unit fixtures — production inventory is the committed
stubs set.

### 9.9 `data/module_attribution.jsonl` (seeded; edit stubs/overlays, not the file)

Governance-surface ownership for every `src/**/*.py`. Sibling of §9.8 — same enumerate →
per-item status → ratchet shape, different denominator. Supports exactly one claim:

> **100% ATTRIBUTED** = every `src/` module is claimed by exactly one surface.

That is **not** "every surface is CLOSED". Statuses stay honestly mixed and advance only in
`docs/governance/closure_authority_index.json`, never in this ledger.

1. `docs/governance/module_attribution_stubs.jsonl` — machine-owned bulk rows
   (`python scripts/analysis/module_census.py --write-stubs …`; path-stable MOD ids).
2. Curated **overlays** supply `owner_surface` and any grade advance.

Modules: `src/governance/module_attribution.py` (registry) + `src/governance/module_census.py`
(discovery/merge); guard: `tests/test_module_attribution.py`.

**Authority pinned:** `"authority": "inventory"` on every line (§6.5). `owner_surface` must
resolve to a `surface_id` in the Closure & Authority Index, or be the `UNATTRIBUTED` sentinel.
`participates_in` is **informational only** and never confers ownership — `CLOSURE IS
BOUNDARY-SCOPED AND NON-TRANSITIVE`.

```python
ModuleAttributionRecord = {
    "id":                     str,   # MOD-NNNN (zero-padded; never reuse)
    "module_path":            str,   # POSIX repo-relative; unique across the ledger
    "owner_surface":          str,   # surface_id | "UNATTRIBUTED"  (exactly one)
    "participates_in":        list[str],  # surface_ids; informational, never ownership
    "regime":                 str,   # DECISION|RESEARCH|PLATFORM|SUBSTRATE|
                                     # MODEL_LINEAGE|TERMINAL|UNKNOWN
    "grade":                  str,   # G0_ATTRIBUTED|G1_DECLARED|G2_AUDITED|G3_CLOSED
    "reachability":           str,   # LIVE_DECISION|BACKTEST_ONLY|TOOLING|
                                     # RESEARCH_ONLY|ORPHANED|UNKNOWN
    "economically_validated": bool,  # per-module; requires grade G2/G3 to be true
    "evidence":               list[dict],  # {path, symbol, type}
    "created":                str,   # ISO-8601 UTC
    "last_validated":         str,
    "notes":                  str,
    "authority":              "inventory",  # PINNED
}
```

Two enforcement axes, deliberately separated. **Enumeration** (every module present exactly
once) is HARD from Phase 1 — a drifting denominator makes any percentage meaningless.
**Attribution** is a monotonic ratchet (`_ATTRIBUTED_FLOOR` in the guard test) so progress
cannot regress; Phase 4 raises the floor to the full module count and the 100% claim becomes
permanent. Only the `DECISION` regime is expected to pursue G2/G3 — a floor asserts that set
stays a small minority of `src/`.

### 9.10 `data/semantic_os/file_identities.jsonl` (Semantic File Identity Layer)

Rename-stable identity for one Python module: `semantic_id (this line's "id") -> semantic_name ->
physical_path`, plus a `filename_semantic_status` classification of whether the physical filename
still matches what the module does. Sixth first-class Semantic OS record kind (`kind:
"file_identity"`) — see `docs/governance/SEMANTIC_OS_V1_DESIGN.md` §3.1 and
`docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md`.

Tier 1/2 (`provenance: "CURATED"`) are hand-authored in `docs/governance/semantic_os/
file_identities.yaml`; Tier 3 (`provenance: "DERIVED"`) is generated at seed time by
`governance.semantic_identity.derive_tier3_identities` for every remaining code-universe path and
is **never** written to the YAML. Both land in this one GENERATED projection, produced by
`scripts/governance/seed_semantic_os.py`; validator: `src/governance/semantic_os.py
::_validate_file_identity`; guard: `tests/test_semantic_identity.py`.

**Authority pinned:** `"authority": "advisory"` on every line (§6.5) — grants no rename or
production authority. `physical_path` is never renamed by this layer.

```python
FileIdentityRecord = {
    "id":                        str,   # dotted lowercase slug, e.g. "engines.candle_polarity_scorer"
    "kind":                      "file_identity",  # PINNED
    "semantic_name":             str,   # human display name, e.g. "Candle Polarity Scorer"
    "physical_path":             str,   # POSIX repo-relative .py path; not under tests/
    "status":                    str,   # ACTIVE|PROPOSED|SUPERSEDED|RETIRED
    "authority":                 "advisory",  # PINNED
    "tier":                      int,   # 1=hand-verified HIGH | 2=boundary-backed MEDIUM | 3=derived LOW
    "confidence":                str,   # HIGH|MEDIUM|LOW (moves with tier)
    "provenance":                str,   # CURATED|DERIVED (moves with tier)
    "derivation":                str | None,  # null if CURATED; "path_slug/v1[#dedupN]" if DERIVED
    "canonical":                 bool,  # exactly one true per physical_path
    "role":                      str,   # CANONICAL|ADAPTER|SHIM|SPLIT_PART|DEAD|UNKNOWN
    "semantic_layer":            str,   # MARKET_STRUCTURE|FEATURE_SURFACE|SCORING|DECISION|RISK|
                                        # EXECUTION|RUNTIME|DATA|CONFIG|GOVERNANCE|RESEARCH|AGENT|
                                        # INTEGRATION|UTILITY|UNCLASSIFIED
    "filename_semantic_status":  str,   # ALIGNED|HISTORICAL|MISLEADING|COMPATIBILITY|SPLIT|UNKNOWN
    "filename_status_reason":    str,   # non-empty for CURATED rows
    "aliases":                   list[str],  # empty for Tier 3 (no reviewed alias claim)
    "concept_ids":               list[str],  # CN-NNN FK, optional
    "miar_entry":                str | None,  # the only hand-authored cross-link
    "summary_50":                str,   # <= SUMMARY_50_MAX chars; empty allowed only if DERIVED
    "why_this_identity":         str,   # empty REQUIRED if DERIVED (unreviewed)
    "evidence":                  list[dict],  # {path, symbol, line, type}; ±30-line drift checked
    "supersedes":                str | None,
    "superseded_by":             str | None,
    "created":                   str,   # ISO-8601 UTC, pinned at seed time
    "last_validated":            str,
    "schema_version":            "semantic_os/1.1",
}
```

Deliberately **excluded** (DERIVED exact-path joins computed in `src/governance/
semantic_objects.py`, never hand-authored on this kind): `owner_boundary`, `encyclopedia_id`,
`script_registry_id`, `imports`, `imported_by`, `tests_importing`. The same five joins are
attached to `OBJ:<path>` records as `semantic_id` / `semantic_name` /
`filename_semantic_status` / `identity_tier` / `identity_provenance` (evidence class `HEURISTIC`
for the first three, `PROVEN` for the last two — see `FIELD_EVIDENCE_CLASS` in
`semantic_objects.py`).

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

## 9.17 `CRTConstructionTrace` JSONL — observation sidecar (Parquet note)

Full row schema for the observation-only `CRTConstructionTrace` stream is maintained with
change class `TRACE_OBSERVATION_JOIN` (emitter: `src/runtime/crt_construction_trace.py`;
default `enabled: false`). This section records the **Parquet projection** contract for
that family so research readers can find it without waiting on an `enabled:true` production run.

**Parquet projection (regenerable sidecar).** Family suffix `_crt_construction.jsonl` →
partition key `engine_state_after` (same CRT-state stratum pattern as `_bar_structure.jsonl`).
Build with `scripts/maintenance/jsonl_to_parquet.py`; query with
`scripts/analysis/query_trace.py` (`--family crt_construction`) via
`src/utils/duckdb_query.open_views`. JSONL remains system of record; measured columns TBD —
no production `enabled:true` run yet.

