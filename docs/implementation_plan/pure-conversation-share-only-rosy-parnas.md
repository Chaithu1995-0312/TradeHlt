# XAUUSD all-layers run — candle flow, Market Context schema, triggerable hypothesis workflows

## Context
`targetschema.txt` (Grok/DeepSeek) is the curriculum view; ChatGPT + user refined it into
(a) HTF ↔ CRT as a coupled Market Context, (b) two rails (backtest vs live), (c) Observation →
Evidence → Decision → Execution. User direction for this plan:
- **Rebuild** per-layer proof artifacts (not reuse) with `run_id` + `trace_id` on every record.
- While analysing, **monitor + code-review** each layer and log defects / bugs / inconsistencies.
- Design as **parallel hypotheses / triggerable workflows**.
- Answer "which way does the candle flow" and design schemas + variables on top of the user/ChatGPT model.
External claims (ChatGPT, DeepSeek) were treated as hypotheses and checked at source (§6.8).

---

## 1. Recorded: which claims hold at source

| Claim | Verdict | Evidence |
|---|---|---|
| HTF is read before CRT classifies the bar | **TRUE** | `backtest_v2.py:2697-2705` reads `parent_feed.bias` + `objective.status`, passes them into `engine.process_candle` |
| HTF and CRT depend on each other both ways | **HALF.** HTF→CRT exists. CRT→HTF **does not exist in code** | `htf_state.py:88-143`: `classify_htf_state(prev, curr)` and `resolve_objective(bias, rng, last_close)` take only parent candles + price. `parent_feed.push(candle)` (`backtest_v2.py:2586`) takes raw candles. No CRT state goes in |
| Structure → HTF → CRT order | **FALSE for the decision.** Structure snapshot is written after the decision | `backtest_v2.py:2716` comment: placed AFTER `process_candle`, observation only. SMC only reaches decisions as feature-vector columns through EngineRunner |
| One shared observation spine feeds both rails | **FALSE.** The live rail has no CRT state machine, no parent CRT, no HTF state | grep of `live_engine_hook.py`, `live_rail_feeder.py`, `live_rail_orchestrator.py`: no `process_candle`, `parent_crt`, `htf_state` (one comment at hook `:969`). Matches F-075 "live has no process_candle loop" |
| A trade becomes a trade at `ExecutionPlannerV1_2.plan()` | **Live rail only.** In backtest, CRT commits first, EngineRunner can veto afterwards | backtest: `TRADE_OPENED` `:2778` → EngineRunner `.run` `:2991`. live: `EngineRunner` `hook:996` → planner `:1021` → `compute_crt_levels` `:1058` → Ultron `:1157` |
| DeepSeek: hook loads `v1_multi_2026_03.json` | **Stale error strings.** It loads `get_prod_metadata()` → `PROD_VERSION` (ACTIVE_VERSION=`v2_htfcrt_2026_08`) | `live_engine_hook.py:288-311` vs `production_config.py:287-295` → DOC_DRIFT candidate |
| `opportunities.parquet` exists | **Known artifact name**; `clean_labels.parquet` still UNVERIFIED | `utils/run_linkage.py` `_ARTIFACT_NAMES` |

**Open disagreement to resolve with the user (not settled by me):**
the user's model says CRT state also shapes HTF context. The code only builds HTF from raw candles.
Both come from the same M15 candles, so today they are linked **by a shared source plus a one-way
gate**, not by a two-way link. Either (a) keep CRT→HTF as a hypothesis and test it (H3), or
(b) build it later as a separately approved behaviour change.

---

## 2. Which way the candle flows

Import arrows show which code uses which. Data moves in its own order. There are two orders:
the backtest works out features for the whole file first and then steps through bars; the live
rail works bar by bar only.

**Backtest rail (per bar, `runtime/backtest_v2.py`)**
```
CSV ─L0─ CandleLoader + validate_dataset
    └─ FeaturePipeline(raw_df)  ← BATCH over whole corpus in __init__ (:2021)
per bar:
  parent_feed.push(candle)            :2586   L4 builds from raw OHLC
  warmup gate                         :2603
  parent_state / parent_objective     :2697   L4 → L3 (one-way)
  engine.process_candle(...)          :2701   L3 decides
  state transition / episode          :2708
  BarStructureSnapshot.emit           :2716   L2 observation, AFTER decision
  TRADE_OPENED                        :2778   trade born (backtest)
  FeatureMonitor drift                ~:2910
  EngineRunner.run (post-commit veto) :2991   L5-L6
  (no planner, no Ultron)                     L7 NOT_REACHED
```
**Live rail**
```
tick → BarBuilder → LiveRailFeeder(rolling FeaturePipeline) → HookedLiveEngine.process
  → FeatureStore(48 keys) → Regime → Drift → StrategyOrchestrator
  → EngineRunner :996 → ExecutionPlannerV1_2 :1021 (trade born, live)
  → compute_crt_levels :1058 → UltronRiskGate :1157 → OrderManager
```
**What the two rails share:** `FeaturePipeline`, `EngineRunner`, `FusionEngine`, `DecisionEngine`.
**Backtest only:** CRT state machine, ParentCRT, HTFState, structure snapshot.
**Live only:** FeatureStore, regime injection, planner, Ultron, orders.

---

## 3. Schemas and variables (designed on top of the user/ChatGPT model)

New dataclasses only; existing variable names are reused as field sources. All records are
observation-only (the decision is already final before they are written, like `BarStructureSnapshot`).

### 3.1 Identity envelope (on every record)
```python
@dataclass(frozen=True)
class RunContext:
    run_id: str            # ONE id per run (replaces the 3 current ids, see H1)
    rail: str              # "backtest" | "live" | "research"
    instrument: str        # "XAUUSD"
    timeframe: str         # "M15"
    active_version: str    # configs/production/ACTIVE_VERSION
    config_hash: str
    schema_hash: str       # feature_schema SCHEMA_HASH (v5.0 / 48)
    dataset_id: str        # data_ingestion.dataset_registry identity
    corpus_path: str; corpus_rows: int
    code_sha: str; tree_dirty: bool

@dataclass(frozen=True)
class TraceContext:
    run_id: str
    trace_id: str          # f"{run_id}:{instrument}:{bar_ts_utc}" — one per bar
    bar_idx: int; bar_ts: str
    span_id: str           # f"{trace_id}:{layer}"
    parent_span_id: str | None
```

### 3.2 Market Context (the coupled HTF ↔ CRT object)
```python
@dataclass(frozen=True)
class HTFContext:                        # sources: parent_feed, htf_state
    parent_timeframe: str                # parent_feed.rule
    parent_candle_id: str                # htf.current_htf_id
    parent_track: str | None             # RANGE_C1 | MANIPULATION_C2 | DISTRIBUTION_C3
    htf_state: str | None                # HTFState
    bias: str | None                     # parent_state
    objective_status: str | None         # parent_objective
    objective_target: float | None; objective_invalidate_at: float | None
    as_of_ts: str                        # last CLOSED parent (point-in-time guard)

@dataclass(frozen=True)
class CRTContext:                        # sources: engine.state
    prev_state: str; crt_state: str      # prev_state / curr_state
    transition: str | None               # f"{prev}→{curr}"
    direction: str | None                # engine.state.direction
    sweep_class: str | None              # crt_sweep_taxonomy
    m15_range_high: float | None; m15_range_low: float | None
    reject_reason: str | None

@dataclass(frozen=True)
class CouplingEdge:
    source: str; target: str
    kind: str        # "gate" | "shared_source" | "hypothesis"
    status: str      # "IMPLEMENTED" | "NOT_IMPLEMENTED" | "UNVERIFIED"
    evidence: str    # file:line

@dataclass(frozen=True)
class MarketContext:
    trace: TraceContext
    htf: HTFContext
    crt: CRTContext
    structure_ref: str | None            # pointer to BarStructureSnapshot row (not inline)
    coupling: tuple[CouplingEdge, ...]
    # default coupling:
    #  OHLC→HTF  shared_source IMPLEMENTED  backtest_v2:2586
    #  OHLC→CRT  shared_source IMPLEMENTED  backtest_v2:2701
    #  HTF→CRT   gate          IMPLEMENTED  backtest_v2:2697
    #  CRT→HTF   hypothesis    NOT_IMPLEMENTED  htf_state:88-143
```
A HTF state × CRT state grid is a derived view of `MarketContext`, not stored separately.

### 3.3 Evidence → Decision → Execution
```python
@dataclass(frozen=True)
class EngineEvidence:   engine: str; score: float | None; passed: bool | None; reason: str | None
@dataclass(frozen=True)
class EvidenceBundle:
    trace: TraceContext
    engines: tuple[EngineEvidence, ...]  # crt, gaussian, zone_gate, rr, trap, bitnet
    strategy_consensus_score: float | None; strategy_consensus_dir: int | None
    regime: str | None; fusion_weights: dict | None
    drift_severity: str | None
    engine_exception: str | None         # H2: caught exception, never hidden again
@dataclass(frozen=True)
class DecisionRecord:
    trace: TraceContext
    fused_score: float | None; approved: bool
    stage: str | None; reason: str | None
    veto_mode: str                       # "pre_commit"(live) | "post_commit"(backtest)
@dataclass(frozen=True)
class TradeObject:
    trace: TraceContext
    birth_site: str                      # "crt_engine_v2.TRADE_OPENED" | "ExecutionPlannerV1_2.plan"
    direction: str; entry: float; sl: float; tp1: float; tp2: float | None
    ttl_bars: int | None; size_hint: float | None
    ultron_decision: str | None          # None = NOT_REACHED on backtest
```

### 3.4 Layer proof (the rebuilt per-layer artifact)
```python
@dataclass(frozen=True)
class LayerProof:
    run_id: str; trace_id: str; span_id: str
    layer: str        # L0..L9
    module: str       # e.g. "config_layer.crt_engine_v2"
    status: str       # PASS | REJECT | NOT_REACHED | EXCEPTION | UNVERIFIED
    input_hash: str; output_hash: str
    artifact_path: str
    note: str | None
```
Written to `results/<run_id>_<INSTR>/layer_proof.jsonl` (+ parquet via existing projection).
`utils/run_linkage.py` gets `layer_proof.jsonl` added to `_ARTIFACT_NAMES` so one `run_id` joins everything.

---

## 4. Workflows as parallel, triggerable hypotheses

**W0 Preflight (runs first, blocks the rest):** `git status --porcelain`, `venv` check, ACTIVE_VERSION,
echo `data/mt5/XAUUSD_M15.csv` path + row count, mint `RunContext`.

Then run in parallel. Each workflow has a trigger, a kill rule, and writes `LayerProof` + findings.

| ID | Hypothesis | Evidence already seen | How to test | Kill rule |
|---|---|---|---|---|
| **H1** | One backtest run creates 3 different run ids, so its outputs cannot be joined by id | `logging_config.RUN_ID` (`:1985`), writer `run_%Y%m%d_%H%M%S` local time (`:1688`), config dump UTC (`:2347`); `run_linkage.py` says artifacts "not addressable from run_id" | Run once and list the id in every artifact | All ids equal |
| **H2** | EngineRunner errors let the trade through, logged only at DEBUG. This could explain F-070's "0 vetoes" | `backtest_v2.py:3023-3025` "Fail-soft: log but allow trade through" | Count `engine_exception` per trace on XAUUSD | 0 exceptions |
| **H3** | CRT → HTF link: is it absent in code, and would it matter? | `htf_state.py:88-143` | Count how many entry *decisions* fall in each HTF × CRT cell (decisions, not bar counts); keep the no-lookahead rule | Result shows no gap the one-way model misses |
| **H4** | The two rails reach different layers for the same bar | §1 grep | Send one bar through both rails; compare the layers each reached | Same layers reached |
| **H5** | The batch feature table can drift out of line with the bar-by-bar loop | `_fv_idx` join + T-16 note `:2040-2068` | Check `feature_vector` time vs `candle.timestamp` on every bar | 0 mismatches |
| **H6** | Errors are swallowed silently inside the bar loop | `except Exception: pass` near `:2920` | List every silent `except` in the loop and count how often each fires | 0 fire |
| **H7** | Live hook error messages name an outdated config file | `live_engine_hook.py:288-409` | Compare the messages with what the code actually loads | Messages already accurate |

**Triggers (use existing surfaces, no new framework):** one thin script per workflow under
`scripts/analysis/layer_trace/` (SITS-registered), plus a `CommandSpec` per workflow in
`src/control_plane/registry.py` so each can be started from `:8787` or the agent, one by one or all together.

**W-Review (runs with every workflow):** code review of each layer module the trace touches. Every
issue gets exactly one §6.8 verdict (`CONFIRMED DEFECT`, `DOC GAP`, …) with file:line. Nothing is
fixed during review.

---

## 5. Next action items (user-added, in order)
1. **Rebuild layer proof records with `run_id` + `trace_id` on every record** (§3.1, §3.4). This is the
   first construction step and starts with H1, because every other test depends on one shared run id.
2. **Monitor + code-review during analysis**: run W-Review alongside H1–H7; record defects, bugs and
   inconsistencies with verdicts; flip or add findings in `docs/current-findings.md` the same turn.
3. **Follow-up:** after H1+H2 results, decide (with the user) whether to fix the run id and the
   silent EngineRunner pass-through. Each fix is its own approved change, run through
   `construction_protocol.py validate-completion`.

## 6. Build order and files
- New, observation-only: `src/runtime/layer_trace.py` (the dataclasses above + emitter, same pattern as
  `runtime/bar_structure_snapshot.py` / `runtime/crt_construction_trace.py`).
- Wire the emitter into `runtime/backtest_v2.py` at the lines in §2, after each decision point (no decision changes).
- `utils/run_linkage.py`: add `layer_proof.jsonl`.
- `scripts/analysis/layer_trace/h1..h7_*.py` + SITS registration; `control_plane/registry.py` CommandSpecs.
- Tests: decision-neutrality (copy `tests/test_bar_structure_decision_neutrality.py`), one-run-id test,
  one-trace-per-bar test.
- `src/` edits → SESSION LOG entry + construction manifest.

## 7. Verification
- Decision-neutrality: XAUUSD trade list identical with tracing on and off.
- Every row in `layer_proof.jsonl` has a non-empty `run_id`, `trace_id`, `span_id`; exactly one trace per bar.
- On backtest, L7 rows show `NOT_REACHED` (not missing).
- `check_governance_invariants.py --all`: failure count no higher than the baseline recorded before the change.

## 8. Decisions for the user
- Should CRT → HTF stay a hypothesis (H3), or be built later as a behaviour change?
- Should fixing H1 (one run id) and H2 (errors letting trades through) happen in this program, or as separate approved changes after the results?
