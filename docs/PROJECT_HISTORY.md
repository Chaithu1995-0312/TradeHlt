# Tradelatest — Project History (April – June 2026)

> **An append-only reconstruction of ~8 weeks of development, tracing how the system evolved**
> from a fragile single-strategy trading engine to a multi-strategy, governance-gated,
> LLM-advisory platform with parallel research infrastructure.
>
> Every claim below is sourced from the `assistant_project.md` session log (1946 lines),
> verified against `CLAUDE.md`, `reports/hidden_wiring_audit.md` (20 findings),
> `reports/runtime_config_reachability.md` (Tier A/H/D/G classifications), `README.md`,
> and the 9 companion docs created on 2026-04-25. File creation dates are used only
> when explicit timestamps are absent from documents.
>
> **Source priority used:** `assistant_project.md` (session log) > reports > docs > file metadata.

---

> ⚠️ **This document is a historical narrative (April–June 2026).**
> It preserves reasoning and mistakes. It is **not operational truth.**
>
> For current operational information, use the living documents in `docs/operations/`:
>
> | Purpose | Document |
> |---------|----------|
> | Which config keys are illusions? | [`docs/operations/KNOWN_ILLUSIONS.md`](operations/KNOWN_ILLUSIONS.md) |
> | Which source to trust for what? | [`docs/operations/TRUST_TIER_INDEX.md`](operations/TRUST_TIER_INDEX.md) |
> | Current system snapshot | [`docs/operations/CURRENT_STATE.md`](operations/CURRENT_STATE.md) |
> | Dependency graph (what breaks) | [`docs/operations/DEPENDENCY_GRAPH.md`](operations/DEPENDENCY_GRAPH.md) |
>
> ---


## Table of Contents

1. [Project Story](#project-story)
2. [Timeline](#timeline)
3. [Major Milestones](#major-milestones)
4. [Architectural Evolution](#architectural-evolution)
5. [Important Decisions](#important-decisions)
6. [Completed Work](#completed-work)
7. [Deferred or Unfinished Work](#deferred-or-unfinished-work)
8. [Current State](#current-state-of-the-project)
9. [Config Illusions Register](#config-illusions-register)
10. [Missing Information](#missing-information)

---

## Project Story

### The Beginning — April 2026

The project started as a reasonably mature but fragile quantitative trading system. By early April 2026, the core was already functional — a CRT (Cascade Retracement Trading) engine, backtesting infrastructure, and a basic production config (`v1_multi_2026_03.json`). But the system had several problems common in early-stage trading systems: hardcoded configuration defaults buried in Python source, a growing test suite with stale tests that didn't match actual APIs, and no documentation that was kept in sync with the code.

**Evidence:** The session log's earliest entries (2026-04-10) reference "session routing decisions deferred at end of AGENTS.md" and "ordered enhancements" — indicating work was already in progress. The `README.md` (§ Quick Start) describes the system as "file-backed quantitative trading system" with the explicit priority stack: `replay correctness > explainability > telemetry continuity > advisory-AI`.

### Phase 1: Foundation Hardening (April 10–18)

The first priority was making the system reliable enough that you could trust it not to silently do the wrong thing.

**JSON as single source of truth.** The team discovered that configuration values were scattered across Python source files as hardcoded defaults. This meant changing a parameter required hunting through multiple files, and there was no single place to audit what values were actually in use. The decision was to move everything into `configs/production/v1_multi_2026_03.json` and eliminate all `.get(key, literal_default)` patterns from Python. Five files were modified in a coordinated sweep: `backtest_v2.py`, `backtest_bitnet.py`, `inout/config.py`, `llama_gate.py`, and the production config itself. Every config-driven field became a `from_prod_config()` classmethod that raised `KeyError` on missing keys. This was completed on April 16.

> **Evidence:** `assistant_project.md` entry dated 2026-04-16: "JSON-as-single-source-of-truth — final 5 files completed." Specifies the exact changes: `model_path` read from `engine_runner` section, `INOUT_DEFAULTS` dict eliminated entirely, `llama_gate` try/except fallback removed, `BacktestConfig` from_prod_config() classmethod added. Summary: "zero config .get(key, literal_default) patterns remain."

**Test suite restoration.** The flip side of the JSON-as-source-of-truth migration was that many tests had been written against APIs that no longer existed. Over several sessions (April 16–25), every stale test was rewritten against actual code. This touched tests across the agent layer (executor, plan_compiler, intent_router, tool_registry), the training pipeline (evaluator, trainer, phase5_calibration, gaussian_update_pipeline), and the engine layer (engine_runner, fusion_engine). The suite went from hundreds of failures to 427 passing, 9 skipped, 2 xfailed on April 16. By April 25, it was at 893 passing — zero regressions across all changes.

> **Evidence:** `assistant_project.md` entries dated 2026-04-16 (427 pass/9 skip/2 xfail), 2026-04-25T00:30 IST (full documentation suite), 2026-04-25T (Flow 4 — four separate test rewrite sessions for executor, plan_compiler, tool_registry, and sklearn guard).

**The documentation burst (April 25).** With the test suite green, the team created a comprehensive documentation suite in a single session: `ARCHITECTURE.md`, `CONVENTIONS.md`, `SCHEMAS.md`, `CONFIG_REFERENCE.md`, `AGENT_REFERENCE.md`, `GOVERNANCE.md`, `TESTING.md`, and `SIGNAL_FLOW.md`. Also created `EXAMPLE_SERVICE.py` as a golden template. The root `CLAUDE.md` was merged (not overwritten), preserving the existing navigator ritual under a new §3 "How to Work With This Codebase" section with a 7-step canonical feature-addition pattern.

> **Evidence:** `assistant_project.md` entry dated 2026-04-25T00:00 IST: 5-file spec delivered (4 new docs + merged CLAUDE.md). Entry dated 2026-04-25T00:30 IST: added 4 deeper references (CONFIG_REFERENCE, TESTING, AGENT_REFERENCE, GOVERNANCE). Cross-links verified live: CLAUDE.md §2 companion-docs table.

### The AI Agent Layer (April 18)

A major design decision was made: build an AI automation agent as a ChatOps overlay on the existing pipeline, not as a replacement for it. The agent operates in three modes:

- **Pipeline orchestrator** — chaining auto_tuner → config_validator → promotion_manager → backtest_v2 → live_engine_hook
- **Live signal copilot** — wrapping EngineRunner → FusionEngine → ExecutionPlanner with `advise.veto`/`resize` (advisory only, UltronRiskGate remains authoritative)
- **Governance meta-reasoner** — driving the promotion loop via `src/governance/orchestrator.py`

Critically, all write operations (promotion, live trading toggles, governance loops) require per-call human confirmation plus a path whitelist guard. The LLM is advisory only, never execution authority.

> **Evidence:** `assistant_project.md` entry dated 2026-04-18: Design doc approved with architecture diagram. "Advisory-only autonomy: every write-tool gated by per-call y/N confirm + path-whitelist guard + existing quality gates."

This decision was refined through two design iterations. In the first pass, the plan allowed the LLM to choose tools and execution order. Jarvis's structural review caught this as a fundamental safety issue. The revised design introduced a deterministic `PlanCompiler` with a hardcoded `PLAN_REGISTRY` — the LLM can classify intent and fill arguments, but cannot decide which tools to run or in what order.

> **Evidence:** `assistant_project.md` entry dated 2026-04-18 (second entry): "Jarvis structural review incorporated. Two critical fixes: (1) PlanCompiler added with deterministic PLAN_REGISTRY; (2) Audit schema extended with per-step and per-session records."

The agent was implemented across 7 modules in `src/agent/` (agent_core, intent_router, tool_registry, plan_compiler, executor, state, audit, cli), with 17 registered tools split across pipeline, copilot, and governance modes. Four prompt files were created (system_copilot, system_governance, intent_router, tool_schema). The agent section was added to the production config with BitNet 3B, REPL-first, and copilot_auto_narrate=false.

> **Evidence:** `assistant_project.md` entry dated 2026-04-18T19:15:00+05:30: "Full implementation — Agent layer + Expansion Engine + LLM Research Pipeline." Lists all 7 agent modules, 4 prompt files, and config additions.

### The Expansion Engine and LLM Research Pipeline (April 18)

Alongside the agent layer, an Expansion Engine was built in `src/expansion/` — a deterministic evolutionary optimizer that mutates config parameters within bounded ranges and scores the results. It uses a `PolicySchema` with `PARAM_BOUNDS`, a `ConfigMutator` for bounded single-parameter mutations, a profit-aware `Evaluator`, and a deterministic `ExpansionEngine` loop with rejection log and expansion trace. The LLM Pattern Extractor uses live `llm_chat` with fallback plans.

> **Evidence:** `assistant_project.md` entry dated 2026-04-18T19:15:00+05:30: "src/expansion/ — 5 modules: policy_schema, config_mutator, evaluator, expansion_engine, llm_pattern_extractor."

The LLM Research Pipeline (`src/llm_research/`) has 4 modules: pattern_extractor (offline LLM → ExtractedPolicy), policy_builder (PolicyEngine deterministic), forward_tester (3-mode: BASELINE/POLICY/HYBRID), and evaluator (generalization, overfitting, contribution analysis).

### The Control Plane (April 17)

The team built a typed HTTP control plane (`src/control_plane/`) with a command registry (`registry.py`), threaded job manager (`job_manager.py`), HTTP API routes (`api.py`), and browser UI. It runs on port 8787 and exposes the full command catalog — replay, backtest, tuning, validation, promotion. A tutorial system with first-run guided tour and playbook was added, along with CLI matrix generation (`scripts/analysis/generate_cli_matrix.py`).

> **Evidence:** `assistant_project.md` entry dated 2026-04-17T16:43:34+05:30: "CRT Web Control Plane implementation (registry + jobs API + UI + docs/tests)." Entry dated 2026-04-17T20:00:27+05:30: "Tutorial navigation implementation (playbook + first-run tour)."

Console encoding was hardened with `SafeStreamHandler` and `safe_print()` in `src/utils/console_safe.py` because Unicode characters in trade output (₹ signs, em-dashes) were causing silent `UnicodeEncodeError` crashes on Windows cp1252 terminals. Tests were added for the fallback behavior and cp1252 replay-path regression.

> **Evidence:** `assistant_project.md` entry dated 2026-04-17T20:21:17+05:30: "Console encoding hardening for replay/backtest and runtime CLI output."

### The Ultron Disambiguation (April 28)

The system had three objects with "Ultron" in their name doing completely different things:

| Name | Role | Location |
|------|------|----------|
| `UltronGovernor` | Regime signal filter in EngineRunner Step 6 | `src/core/ultron_gate.py` |
| `UltronRiskGate` | Capital protection layer after ExecutionPlanner | `src/core/ultron_risk_gate.py` |
| `UltronRiskGateWrapper` | Pre-scaler utility (orphaned, not wired in production) | `src/core/ultron_risk_gate_wrapper.py` |

The critical problem was that `ultron_gate_enabled` in the config sounded like it controlled the risk gate but actually controlled the governor. This naming confusion was corrected: the canonical names became `RegimeGovernor` / `UltronRiskGate` / `UltronRiskGateWrapper`, with backward-compatible aliases. Six files were touched, zero dangling references remained.

> **Evidence:** `assistant_project.md` entry dated 2026-04-28: "Full oven internals — 4 scoring engines + EngineRunner 8-step wiring + Ultron naming disambiguation + codebase reachability map." Lists all 8 steps, the exact formula `s_final = 0.35×s_sweep + 0.25×s_breakout + 0.20×s_retest + 0.20×s_time`, and the "KEY GOTCHA: ultron_gate_enabled sounds like it controls UltronRiskGate but actually controls UltronGovernor."

> **Second entry dated 2026-04-28:** "Canonical naming convention enforced — RegimeGovernor / UltronRiskGate / UltronRiskGateWrapper" across 6 files, with grep verification: "ZERO dangling references."

### The RR Engine Data Integrity Audit (April 30)

A worrying hypothesis emerged: the RR engine might have been returning a constant `rr=2.0` for all trades, meaning the fusion scores had been receiving a non-discriminating input. A full audit found a more nuanced picture, documented in `docs/RR_DATA_INTEGRITY_AUDIT_2026_04_30.md`:

1. **FINDING 1 — `models/rr_dataset.json` was DEGENERATE.** All `y_rr=0.0`, all `y_win=0`, with 11 features instead of 35. `load_dataset()` would crash at row 0 due to vector length mismatch — it was **inert**, not silently corrupting.
2. **FINDING 2 — Tuner JSONL logs were CLEAN.** 96+ files sampled, zero RR contamination. Tuner optimized on CRT S-score only.
3. **FINDING 3 — Old engine rr=2.0 was real but LOW IMPACT.** Constant 0.667 score × 20% weight = 0.133 contribution to every fusion score. Non-discriminating but stable.
4. **FINDING 4 — Phantom import in `rr_pattern_miner.py`** (`from features.feature_schema import RR_SCHEMA` — symbol didn't exist) was fixed.

> **Evidence:** `assistant_project.md` entry dated 2026-04-30: "RR engine data integrity audit — rr=2.0 contamination investigation." All 4 findings with detailed evidence per finding.

### The PromotionManager Fix (April 29)

A critical governance bug was discovered: `PromotionManager._write_to_registry()` was writing sparse tuner entries (9 top-level keys only) as the promoted config. Any call to `get_prod_section("llama_gate")` on the new version would raise `RuntimeError` because the key didn't exist. This caused 393 test failures on next import.

The fix was a `_load_full_base_config()` method that:
1. Tried `BASE_VERSION_FALLBACK` ("v1_multi_2026_03") first
2. Checked for `FULL_CONFIG_SENTINEL` key (`"engine_runner"` — only full configs have it)
3. Fell back to scanning registry by mtime for any full config (skipping archived)
4. Deep-cloned the base and overlaid only 8 metadata keys from the tuner entry

The already-promoted `v2_multi_2026_04.json` was retroactively patched with full engine sections inherited from `v1_multi_2026_03`.

> **Evidence:** `assistant_project.md` entry dated 2026-04-29: "PromotionManager merge-into-base strategy — governance gap fix." Includes the exact constants (`_FULL_CONFIG_SENTINEL`, `_BASE_VERSION_FALLBACK`), 3 changes, and retroactive patch confirmation.

### The Backtest Feature Pipeline Bug (April 26)

All feature columns in `_trades.csv` were zero. Root cause was three compounding bugs:

1. **Bug 1 (primary — off-by-one + warmup offset):** FeaturePipeline dropped ~50 NaN warmup rows and reset index to 0, but the backtest loop used 1-based candle index on ALL raw candles. Near EOF, the lookup exceeded feature vector length and returned zero fallback.
2. **Bug 2 (silent failure):** FeaturePipeline construction had no try/except. Capitalized CSV headers crashed silently, leaving `feature_vectors=None`.
3. **Bug 3 (column mismatch):** FeaturePipeline required lowercase headers ("timestamp", "open", "high", "low", "close"); `pd.read_csv()` passed raw uppercase headers.

**Fix:** (a) Lowercase + merge split date/time columns before FeaturePipeline. (b) try/except around pipeline init with graceful fallback. (c) Build `self.feature_ts_to_idx: dict[pd.Timestamp, int]` for O(1) dict lookup immune to off-by-one errors.

After the initial pd.Timestamp fix (April 26), a second issue emerged: `pd.Timestamp` objects from `pd.to_datetime(string)` vs `pd.Timestamp(naive_datetime)` silently fail dict equality due to tz-awareness or nanosecond precision differences. Fix: `strftime("%Y-%m-%d %H:%M:%S")` normalization.

> **Evidence:** `assistant_project.md` entry dated 2026-04-26: "Root-cause and fix — all feature columns zeroed in _trades.csv." Lists all 3 bugs and the fix steps. Second entry same date: "Fix pd.Timestamp key mismatch — Universe-A batch features still all-zero."

### The Unified Bridge (April 26)

A "Unified Bridge" architecture was implemented to capture live engine metrics at trade entry and write them alongside batch features in `_trades.csv`. `CRTEngine.get_live_metrics()` returns `live_atr`, `live_ema_fast`, `live_ema_slow`, `cached_retest_depth`, `cached_body_ratio`, `cached_disp_strength`, `cached_session`, and `cached_double_sweep` — all entry-candle accurate.

The `TradeRecord` gained 8 new audit fields, and `to_csv_rows()` writes Universe-A canonical features first, then Universe-B audit columns. A zero-feature warning triggers when >50% of batch features are 0.0, distinguishing live-engine failure from batch-lookup failure.

> **Evidence:** `assistant_project.md` entry dated 2026-04-26: "Unified Bridge — event-driven live metrics + execution audit columns in _trades.csv."

### Groq without openai (April 26)

The `openai` package dependency was eliminated. The Groq integration in `llama_gate.py` was rewritten to use pure `urllib.request` — a direct POST to `https://api.groq.com/openai/v1/chat/completions`. This removed the `_GROQ_CLIENT` global, the lazy SDK factory, and the `from openai import OpenAI` import.

> **Evidence:** `assistant_project.md` entry dated 2026-04-26: "Remove openai package dependency — replace Groq client with stdlib urllib." Lists removed globals, added functions (`_groq_available()`, `_groq_request()`) and test rewrites.

### The Sprint Sequence (April 30 – May 1)

This was the most intense implementation period — building 10 trading strategies and full production infrastructure in three days:

**Sprint 1 (April 30):** Foundation layer — `StrategyResult` dataclass with BUY/SELL geometry validation + INR cap enforcement, `BaseStrategy` with lot sizing via `usd_to_inr_rate` from config, `HistoricalFetcher` for TimescaleDB with `ON CONFLICT DO NOTHING` idempotent inserts, and `LLMLogger` for structured anomaly logging at export time.

> **Evidence:** `assistant_project.md` entry dated 2026-04-30 (Sprint 1). Key decisions: "StrategyResult.validate() enforces BUY/SELL geometry + INR cap; LLMLogger anomalies detected at export() time."

**Sprint 2 (April 30):** Five strategies — CRT Wrapper (adapter over `engines.crt_engine.compute()`, zero CRT changes), Mean Reversion (RSI+BB: `rsi_14 < 30` + price at BB lower → BUY), Breakout (BOS + swing level + `volume_ratio >= 1.3` breakout, SL anchored at broken swing level), Pattern Recognition (Hammer/ShootingStar/BullEngulf/BearEngulf/Marubozu, 3-candle state buffer), Trap Strategy (BULL TRAP → SELL / BEAR TRAP → BUY, LIQ_SWEEP intent variant with confidence ladder: +0.15 liquidity_sweep, +0.10 disp_strength, +0.10 double_sweep, +0.10 volume_ratio > 1.5). Config sections added to `v1_multi_2026_03.json`.

> **Evidence:** `assistant_project.md` entry dated 2026-04-30T12:15Z. Key fix: "S9 hammer upper_wick condition changed from body*0.3 to total_range*0.15 (body can be tiny on doji-hammers)."

**Sprint 3 (April 30):** Five more strategies — Stat Arb (EMA-spread Z-score: `z > 1.5` → revert, trend filter blocks strong-trend fades), Grid (ATR-grid on swing range, lower-half levels → BUY, upper → SELL, TRENDING regime blocked), Scalping (MACD-hist + momentum + session filter 07:00–17:00, 2-bar cross detection), News Sentiment (Layer 1: `volatility_ratio >= 2.0` or `spread > 0.05%` → NO_TRADE, Layer 2: zone + trend follow), ML Ensemble (optional BitNet blend + weighted feature scorer, 4-indicator majority vote for direction). Config sections added to `v2_multi_2026_04.json`. A key realization: "v2_multi_2026_04 is ACTIVE version, not v1_multi_2026_03 — all config edits now go to v2."

> **Evidence:** `assistant_project.md` entry dated 2026-04-30T13:00Z. Key fixes: S8 MACD score denominator from `atr` to `atr * 0.1`, S8 min_score lowered to 0.45 for feature-only mode.

**Sprint 4 (April 30):** The `StrategyOrchestrator` — runs all 10 strategies per candle with completeness gate (`min_signal_strategies = 2`), consensus gate (`min_agreement_ratio = 0.60`), weighted score/confidence aggregation, and per-strategy exception isolation (`fail_open = True`). The `FusionEngine` gained `fuse_strategy_results()` to absorb orchestrator output. Config: strategy weights ranged from S1=0.20 down to S8=0.06. 929 tests passed (+36 new).

> **Evidence:** `assistant_project.md` entry dated 2026-04-30T14:00Z.

**Sprint 5 (May 1):** UAT infrastructure — `MonteCarloEngine` (bootstrap resampling, `MIN_TRADES = 10` guard, P(ruin), equity distribution p5/p50/p95), `KillSwitch` (JSON-persisted daily/weekly loss gate with date-rollover, manual reset, `status_dict()` with 8 keys), `UATRunner` (7 UAT areas covering signals, simulation, alerts, scoring, Monte Carlo, kill switch scenarios, and 8 edge cases: EC-01 zero_atr through EC-08 all_zeros). 946 tests passed (+17 new).

> **Evidence:** `assistant_project.md` entry dated 2026-04-30T18:00Z.

**Sprint 6 (May 1):** Live integration — `TelegramBridge` (optional-import requests, `send_signal_alert()`, `send_kill_switch()`, `send_daily_summary()`, `dry_run = True` default), `MT5Bridge` (optional-import MetaTrader5, `send_order()` with lot size clamped to `[lot_min, lot_max]`, `dry_run` enforced when MT5 not installed), and wiring into `live_engine_hook.py` with kill switch pre-check, StrategyOrchestrator, Telegram alert on UltronRiskGate APPROVE, and MT5 order placement. 972 tests passed (+26 new).

> **Evidence:** `assistant_project.md` entry dated 2026-05-01T01:00Z. Bug fix noted: "MT5Bridge.connect() with enabled=False now sets _connected=False (not True)."

**Sprint 7 (May 1):** Production governance — `StrategyBacktester` (forward-scan simulation: BUY/SELL checked against next `max_forward_candles` bars, `Composite score = 0.35*WR + 0.30*PF + 0.20*DD + 0.15*vol`), `MultiStrategyValidator` (3 hard gates: min trades, win rate >= 0.30, max drawdown <= 75K INR), `HealthChecker` (stdlib HTTP on port 8788: `/health` and `/status` endpoints, daemon thread), `Dockerfile` (Python 3.10-slim, EXPOSE 8787 8788), `scripts/governance/promote_v2.py` CLI. 1001 tests passed (+29 new).

> **Evidence:** `assistant_project.md` entry dated 2026-05-01T01:30Z. Bug fixes: "synthetic CSV in tests used invalid timestamps (hour 24+) → fixed using datetime+timedelta."

### Performance Improvements (April 28)

Eight bottlenecks were identified in the backtest pipeline via code inspection of `backtest_v2.py`, `auto_tuner_multi.py`, and `feature_pipeline.py`:

| Priority | Bottleneck | Fix |
|----------|-----------|-----|
| P1 CRITICAL | FeaturePipeline re-runs per tuner parameter set × instrument | `skip_features=True` flag on BacktestRunner |
| P2 HIGH | CandleLoader tries 8 timestamp formats per row | Cache detected format after first parse |
| P3 HIGH | `CANONICAL_FEATURES.index()` called in candle loop | Precompute `{feature_name: index}` dict in `__init__` |
| P4 MEDIUM | `_session()` iterates session_windows dict on every candle | Precompute 24-entry hour→session lookup dict |
| P5 MEDIUM | `max_drawdown_pct` scans entire equity_curve list | Maintain running max drawdown in `apply_trade()` |
| P6 MEDIUM | Tuner workers write 4 report files per eval (never read) | `write_reports=False` flag on `BacktestRunner.run()` |
| P7 LOW | `_rolling_win_rate` is O(n × window) | Sliding window counter → O(n) |
| P8 LOW | `bt_log` file handler at DEBUG floods disk during tuning | Raise log level to WARNING via config key |

P1 was implemented in the same session: a `skip_features: bool = False` kwarg on `BacktestRunner.__init__`, guarded the FeaturePipeline block with `if self.csv_path and not skip_features:`, and patched all 3 tuner scripts (`auto_tuner_multi.py`, `auto_tuner.py`, `auto_tuner_gemin_pro.py`) to pass `skip_features=True`.

> **Evidence:** `assistant_project.md` entry dated 2026-04-28: "Backtest performance improvement plan — 8 bottlenecks identified, plan document created." Second entry same date: "P1 implemented — skip_features=True in all three tuner workers."

### The Shadow System and Phase Experiments (May 27 – June 10)

**Phase 0 — Telemetry (May 27):** A `TelemetryCollector` class (~200 lines, passive sidecar, zero behavior change) was added to `crt_engine_v2.py`, emitting 5 event types: state transitions (`on_state_entered`), expansion checks (`on_expansion_retrace_check`), resets (`on_reset`), candidate scores (`on_candidate_score` + `on_decision_distance`), and candidate acceptance (`on_candidate_accepted`). Running BNBUSDT backtest (14,016 candles) produced 2,649 telemetry records.

**Phase 0 Findings (all structural unknowns answered):**

| Metric | Value | Prior Hypothesis |
|--------|-------|-----------------|
| SWEEP count | 600 | — |
| DISPLACEMENT count | 154 | — |
| EXPANSION count | **8** | ~184 (wrong by **23x**) |
| RETEST count | 7 | — |
| EXECUTION count | 2 | — |
| SWEEP→DISPLACEMENT | 25.7% | — |
| **DISPLACEMENT→EXPANSION** | **5.2%** | ← PRIMARY BOTTLENECK |
| EXPANSION→RETEST | **87.5%** | Hypothesis was 180° wrong |
| RETEST→EXECUTION | 28.6% | killed by zone/session filter |
| Reset attribution: HTF_CHANGE | **98.1%** | — |
| Reset attribution: Retrace | 1.3% | — |
| Decision distances: 0 near-misses | All approved | S-score not a bottleneck |

This completely revised the optimization strategy: shadow displacement protection became the primary lever, not soft-conf tuning. Two proposed candidates were INVALIDATED (retest_depth_max and soft_conf_max_candles).

> **Evidence:** `assistant_project.md` entry dated 2026-05-27T07:55Z. Full table of true episode counts, survival rates, reset attribution, and plan revision.

**Phase 1 — Shadow Displacement Protection (May 27):** A `SHADOW_PENDING` state was added to the CRT state machine (8→9 states). When a displacement occurs during an HTF reset, instead of discarding the candidate, the engine enters SHADOW_PENDING with a TTL of 4 candles. If a matching expansion occurs within that window, the candidate is recovered.

**Phase 1 results (70,080 candles, 4× speed):**

| Metric | Before (Phase 0b) | After (Phase 1) |
|--------|-------------------|-----------------|
| EXPANSION episodes | 8 | 93 (24 normal + 69 shadow) |
| Trades | 2 | 14 |
| Win Rate | — | 71.4% |
| Avg RR | — | 0.49R |
| Net PnL | — | +6.83R |
| SHADOW_LEAK | — | 0 (hard gate) |
| Shadow recovery rate | — | 69/379 = 18.2% |

> **Evidence:** `assistant_project.md` entry dated 2026-05-27T08:30Z. All decision gates PASSED.

**Phase 3b — Expired Counterfactual RR Gate (May 27–28):** This gate tested whether the TTL was correctly cutting stale structures. 7 expired candidates were simulated via `scripts/analysis/p3b_gate_expired_counterfactual_rr.py`. 6/7 had no qualifying retest in a 200-candle window. 1 simulated trade (CAND-27492 LONG) had rr=-1.0 (SL hit). Mean counterfactual RR = -1.0 (N=1). **Verdict: TTL correctly cuts stale structure. PASS PROMOTION GATE.**

> **Evidence:** `assistant_project.md` entry dated 2026-05-28T01:00Z: "Script: scripts/analysis/p3b_gate_expired_counterfactual_rr.py. ceiling=0 for 2 candidates (no retrace in expansion) → ATR fallback applied."

**Phase 4b — Shadow Age-Decay Gate (May 27–28):** Implemented `shadow_age_penalty_lambda` — an exponential decay applied to shadow candidates before they reach execution. Experiment matrix: λ = 0.00, 0.10, 0.20, 0.35 with variants B1–B3 (norm=4 reparametrization).

| Run | λ | norm | Shadow Trades | Shadow RR | Normal Trades | Normal RR | DD | WR |
|-----|---|------|--------------|-----------|--------------|-----------|-----|-----|
| A0 | 0.00 | 0 | 22 | -0.290 | 15 | +0.314 | 9.23R | 45.9% |
| A1 | 0.10 | 0 | 22 | -0.290 | 15 | +0.314 | 9.23R | 45.9% |
| A2 | 0.20 | 0 | 4 | -0.394 | 15 | +0.336 | 3.18R | 52.6% |
| A3 | 0.35 | 0 | 0 | n/a | 15 | +0.328 | 2.08R | 60.0% |

**KEY FINDING: `shadow_quality_improves = FALSE`.** At λ=0.20 (4 survivors), RR WORSE at -0.394 vs baseline -0.290. Score is inversely correlated within shadow group. Decay = pure threshold shifting.

**Verdict:** `shadow_advisory_only = True` applied to production config. Normal-only baseline: 15 trades, 60% WR, avg_RR = +0.328, drawdown **reduced 77%** from 9.23R to 2.08R.

> **Evidence:** `assistant_project.md` entry dated 2026-05-28T00:00Z: Full inspection table, A/B parity confirmed, "shadow_advisory_only: false → true" in production config. Entry dated 2026-05-27T15:26:31Z: implementation details — all 9 changes listed.

**Phase 5 Plan (May 28):** Architecture: **CRT (discover) → TTL (bound) → Decay (govern) → Threshold (rank).** Planned:
- Phase 5a: Replay Selectivity Sweep — `tier_2_threshold = [0.44..0.60]`, 7 backtest runs
- Phase 5b: Reject Audit — simulate `outcome_if_taken` for LOW_SCORE rejects
- Phase 5c: Telemetry additions — rename `_age` → `_cross_window_distance`, add `approval_path`/`context_source`/`decision_distance` to `CANDIDATE_LIFECYCLE`, add `_htf_transition_distance` to EngineState

> **Evidence:** `assistant_project.md` entry dated 2026-05-28T01:00Z. Phase 5c details: "Add approval_path: NORMAL|SHADOW|SHADOW_DECAYED|SHADOW_BLOCKED."

### The Direction-Mirroring Discovery (May 13)

A critical machine learning insight: the opportunity scanner emits both long and short signals per candle with identical 35-dim feature vectors. This creates contradictory training examples that cancel signal. Training on long-only data achieved corr=+0.2027 APPROVED vs corr=+0.0062 on combined data.

The fix was direction-mirroring in `phase5_calibration.py`: short records have 10 directional features negated (`_MIRROR_NEGATE_FEATURES`) and 2 pair-swapped (`_MIRROR_SWAP_PAIRS`) before training. The active production model `v4_mirrored` achieves corr=+0.2066, CV stable (std=0.0072), trained on 242K samples.

> **Evidence:** `assistant_project.md` entry dated 2026-05-13: "Phase 2 — Registry cleanup, first promoted model, direction-mirroring fix." 10 verifications listed including "active=v4_mirrored, corr=+0.2066, _P5_PARAMS empty (0 schema_checksum matches)."

The mirroring was also wired into inference-side through `GaussianScorer.compute(features, candle_idx, direction='long')`. For `direction='short'`, it calls `_mirror_features_for_short()` before scoring. Constants `_GMIRROR_NEGATE` and `_GMIRROR_SWAP` were added to `model_registry.py` and kept in sync with the training-side constants.

**Direction threading chain (verified complete end-to-end):**

```
opportunity_scanner (long+short)
  → phase5 mirror_short
    → v4_mirrored (APPROVED, corr=+0.2066)
      → load_active_gaussian_scorer
        → GaussianScorer.compute(direction=)
          → mirroring
            → backtest_v2 Phase-5 gate (engine.state.direction.value.lower())
              → engine_runner (input_data["direction"] int → _gauss_dir str)
                → HeuristicGaussianEngine (direction ignored, compat kwarg)
                → MLGaussianEngine (mirrors when direction="short", GAUSSIAN_IMPL=ml)
                  → live_engine_hook (strategy_consensus_direction → engine_input["direction"])
```

> **Evidence:** `assistant_project.md` entries dated 2026-05-13 (all 3 sessions): Phase 2 (thread direction kwarg into backtest_v2), Phase 3 (engine runner direction threading), Full verification with 8 sanity invariants ALL PASS.

### The Two-Layer Architecture (May 12)

A significant architectural decision: split the system into **Pipeline A (Runtime)** — backtesting, governance, live trading — and **Pipeline B (Research)** — unbiased training, opportunity discovery, pattern extraction. The research pipeline runs in isolation; it cannot influence production decisions.

Key new components:
- `scripts/research/opportunity_scanner.py` — discovers trade opportunities from CSV
- `scripts/research/discover_zones.py` — zone detection for structure-based trading
- `scripts/analysis/compress_logs_for_llm.py` — compresses trade logs for LLM context window
- `scripts/groq_bridge/apply_llm_suggestions.py` — applies LLM suggestions back to training
- `scripts/auto_train_from_opportunities.py` — auto-training pipeline from discovered opportunities

Modified: `src/core/model_registry.py` (added `GaussianScorer`, `NoOpScorer`, `load_active_gaussian_scorer`), `src/runtime/backtest_v2.py` (emptied `_P5_PARAMS` literal, `CRTCalibratedScorer` now delegates to registry), `scripts/training/phase5_calibration.py` (added `--opportunities`/`--feature-subset`/`--class-weights`/`--rr-buckets` flags).

> **Evidence:** `assistant_project.md` entry dated 2026-05-12: "Two-Layer Architecture Migration (Pipeline A Runtime + Pipeline B Research)." Lists all files created and modified. "NOT TOUCHED: src/core/engine_runner.py."

### The Hidden Wiring Audits (June 6)

Two deep audits of config-to-code wiring were performed on the same day.

**Hidden Wiring Audit — 20 findings across Types A–G:** Produced `reports/hidden_wiring_audit.md`. Key outcomes:
- **Type A (Dead Config):** #1 capital_management (10 keys, zero consumers), #2 data_ingestion (points to nonexistent PostgreSQL), #3 gate_intelligence (5 keys with weight/threshold, zero consumers in spine), #4 sl_tp_comparison (self-declared dead), #10 signal_belief, #11 cognitive_layer, #14 phase5_calibration
- **Type D/G (Split Brain / Runtime Divergence):** #9 ultron_gate_enabled:false creates backtest-vs-live divergence — backtest at false produces inflated trade counts and win rates that don't reflect live behavior at true
- **Type D (Split Brain):** #18 INOUT vs CRT risk limits unbounded — worst-case 13 concurrent positions (3 INOUT + 10 CRT)
- **Type F (Config Drift):** #20 fitness_weights schema mismatch, #16 missing execution_planner keys
- **Type C (Shadow Override):** #7 PROMOTION_MARGIN=2% hardcoded in `model_registry.py`, not configurable

> **Evidence:** `assistant_project.md` entry dated 2026-06-06 19:45 UTC+5:30. Full finding classification and next steps. Source: `reports/hidden_wiring_audit.md`.

**Runtime Config Reachability Audit — Tier separation with source confirmation:** Produced `reports/runtime_config_reachability.md`. Key source-confirmed corrections:
1. **Ultron** naming illusion resolved: `ultron_gate_enabled` (line 44 in config) → controls RegimeGovernor inside EngineRunner (confirmed via source read of `engine_runner.py:421, 853`).
2. **decision_engine.score_threshold** confirmed H-class illusion: read from config (line 93), stored but NEVER used. Effective threshold comes from `DynamicThreshold.compute()` → percentile(scores, 85) clamped [0.45, 0.65]. Config value 0.45 only serves as lower clamp bound.
3. **fitness_weights** documentation (`SCHEMAS.md §5.1`) confirmed WRONG: `config_validator.py:132-136` reads key names `expectancy_rr`, `trade_count_norm`, `drawdown` — which match config. Code follows config. SCHEMAS.md is documentation-only drift.
4. **execution_planner** keys (`min_rr_ratio`, `default_sl_atr_mult`, `liquidity_*`) confirmed NEVER consumed by planner. SL/TP/RR delegated to `gate_intelligence.compute_crt_levels()`.
5. **gate_intelligence** corrected from H-class (Dead Config in hidden_wiring_audit) to D (Execution) — gate IS wired via ExecutionPlanner.
6. "wrong configs promoted" risk **DOWNGRADED from CRITICAL to MEDIUM**: code matches config, only SCHEMAS.md is wrong.
7. **12 confirmed H-class illusions** with per-finding confidence.

> **Evidence:** `assistant_project.md` entry dated 2026-06-06 20:22 UTC+5:30. Source: `reports/runtime_config_reachability.md` — all Tier A findings cross-referenced against actual code.

### Architecture Migration Doctrine (May 28)

The north star was formalized in `assistant_project.md`'s header block: **"LLM context economy — migrate toward an event-driven LLM-event-microservices architecture so a future LLM loads only the one service it needs instead of the whole codebase."**

**Priority order (ranks above refactor speed):** replay correctness > explainability > telemetry continuity > advisory-AI > (structure validity ≠ execution validity)

**Five governance questions** — apply as a pre-merge checklist to every change:
1. Does replay remain deterministic?
2. Does telemetry remain comparable across runs?
3. Can this state be audited later?
4. Can an LLM reason about this event?
5. Is execution authority still isolated?

**Standing rules:**
- Consolidate on `src/events/event_fabric.py` — never fork the event system
- LLMs are advisory governance, never execution authority
- No lookahead in replay; deterministic seeds mandatory
- New telemetry is additive; no field removed without documented superseding

**Five migration phases (M0–M5):**
- M0 — Map & doctrine (COMPLETED May 28: CODEBASE_STATE_MAP.md, EVENT_TAXONOMY.md, SERVICE_BOUNDARY_MAP.md, REPLAY_GOVERNANCE.md, LLM_GOVERNANCE_LAYER.md, services/_TEMPLATE.md, services/decision_spine.md)
- M1 — Telemetry normalization (NOT IMPLEMENTED)
- M2 — Event extraction (NOT IMPLEMENTED)
- M3 — Orchestration de-coupling (NOT IMPLEMENTED)
- M4 — Dependency inversion (NOT IMPLEMENTED)
- M5 — LLM-layer hardening (NOT IMPLEMENTED)

> **Evidence:** `assistant_project.md` header block (lines 14–77) and entry dated 2026-05-28T20:00Z. "M0 DOCS (docs/architecture/) — 5 files + this doctrine header + services/ templates."

### The Edge Discovery Program (June 9–10)

A new research platform parallel to the live CRT spine. The commitment (frozen in `assistant_project.md`): **"discover, explain, validate, monitor, retire statistically robust market behaviors without privileging any belief."**

**M1 (June 9):** Behavior-agnostic measurement core — `src/research/contracts.py` (Signal, Outcome, EdgeReport, MetaProfile, Hypothesis Protocol), `src/research/measurement/forward_walk.py` (lifted opportunity_scanner trailing-stop convention + `time_to_tp`/`time_to_failure`/`reached_1r` + no-lookahead guard), `measurement/metrics.py` (EdgeAggregator: WR/PF/expectancy/MFE-MAE percentiles/continuation_prob/drawdown). 11 tests passed.

> **Evidence:** `assistant_project.md` entry dated 2026-06-09: "Edge Discovery Program — Phase 0 plan frozen + M1 measurement core shipped."

**M2 (June 9):** Cost model (`CostModel` flat 12 bps round-trip: 0.05+0.05+0.02%), controls immune system (`random_baseline` uniform 50/50 + biased 70/30, `always_long` anti-drift), hypothesis plugin layer (`@register_hypothesis` + `HYPOTHESIS_REGISTRY`), and two hypotheses: `expansion_breakout` (continuation) and `mean_reversion` (anti-bias proof). 21 tests passed. Real-data smoke test on BTCUSDT (4000 candles): all 5 plugins fire through one pipeline producing NET EdgeReports. **Anti-bias guard confirmed** — measurement core contains no `.family` reference.

> **Evidence:** `assistant_project.md` entry dated 2026-06-09: "Edge Discovery Program — M2 (cost model + controls immune system + hypothesis plugin layer)."

**M3 (June 10):** Deterministic `HypothesisRunner` over a universe of CSVs — per-(hypothesis, instrument) plus pooled `EdgeReport`. Config from `research_config.json` (no magic numbers in Python). Byte-identical determinism proven: `always_long` run twice over 346,082 signals across 11 instruments (`*_M15.csv`) produced identical `edge_report.json` with same sha256 `35a73f03...`. 24 tests passed.

> **Evidence:** `assistant_project.md` entry dated 2026-06-10: "Edge Discovery Program — M3 (deterministic HypothesisRunner + research CLI)." "REAL-DATA PROOF: ran always_long twice over universe into separate dirs → edge_report.json byte-identical."

### The Session Sweep and OOS Validation (June 9–10)

On June 9, a consensus sweep across 15 parameter combinations (`min_consensus_signals 1-3 × min_consensus_agreement 0.50-0.70`) returned NULL — all results were bit-identical. Root cause: those parameters route only through `FusionEngine.fuse_strategy_results()`, which is dormant (`weight_strategy_consensus=0.0`). The live gate uses `_decide() → tier_*` in `fusion_engine.py:670`. A latent fix was applied: `engine_runner.py:389-390` now reads the two consensus keys into `FusionConfig` (they were silently defaulting).

This led to the discovery that `session_sweep.py` was broken on the `patch` branch — it read `profit_factor`/`annualized_return_pct`/`return_to_max_dd`/`funnel_counts` fields that didn't exist on `BacktestMetrics`. A full ROI/PF metrics layer was built TDD-style per `test_roi_metrics.py` + `test_roi_gaps.py`:

- `_ROI_DEFAULTS` with 7 new BacktestMetrics fields
- `MetricsEngine._roi_block` — post-hoc, `pnl_rr_net` only, span-aware CAGR
- `funnel_counts = dict(state_counts)`
- `config_validator._aggregate_metrics` — `total_return_pct_across` (additive, not in final_score)

**CRITICAL CHECKPOINT PASSED:** session_sweep V0 hard gate reproduced published baseline exactly: **15 trades, PF=1.7929, +4.91% ROI** — proving the math. **Bonus finding:** V1 (+ASIA) lifted 15→23 trades, PF 1.79→2.54, ROI +4.91%→+13.29%, maxDD flat — confirming **Phase 6b session-filter-is-#1-lever**.

> **Evidence:** `assistant_project.md` entry dated 2026-06-09: "Consensus sweep NULL → ROI/PF metrics layer (TDD) → session_sweep restored."

**OOS Validation (June 10):** Ran `session_sweep.py --train-split 0.7` with resolver `resolve_allowed_sessions` confirmed restored. Prod resolves to `v2_multi_2026_04`. Incumbent = restrictive V0 (LONDON, NEWYORK, OVERLAP).

**Verdict: KEEP_INCUMBENT — no promotion.**

| Variant | IS ROI | OOS ROI | OOS PF | Retention | OOS Monthly ROI | G1 Pass? |
|---------|--------|---------|--------|-----------|----------------|----------|
| V0 (incumbent) | — | — | — | — | +0.15% | — |
| V1 (+ASIA) | +13.29% | OOS-robust | 3.25 | 1.24 | **+0.63%** | No (+0.48pp < +1pp) |
| V2 (OFF_SESSION) | — | — | — | **0.19** | — | No |
| V3/V4 | +17.11% (artifact) | — | — | 0.59 < 0.70 | — | No |

+ASIA was OOS-robust (retention 1.24, OOS expectancy +0.653R) but failed **only G1's absolute floor**: OOS monthly ROI +0.63% vs incumbent +0.15% = +0.48pp below +1pp bar. OFF_SESSION did NOT survive OOS (retention 0.19 for V2; V3/V4 at 0.59 < 0.70 threshold). **Governance correctly refused churn.**

> **Evidence:** `assistant_project.md` entry dated 2026-06-10: "BNBUSDT session OOS/G1 evaluation — KEEP_INCUMBENT (no promotion)." All 4 session variants evaluated, Step 3 (promotion) NOT triggered.

---

## Timeline

| Date | Event | Evidence |
|------|-------|----------|
| 2026-04-10 17:02Z | Continue ordered enhancements (baseline + schema gate alignment) | assistant_project.md |
| 2026-04-10 17:37Z | Enforce persistent response logging mandate in AGENTS.md + CLAUDE.md | assistant_project.md |
| 2026-04-10 18:25Z | Phase 1 runtime-hook contract hardening + production validation automation | assistant_project.md |
| 2026-04-10 18:32Z | Phase 2 fusion path toggle hardening (`fusion_compare_evaluate`, `fusion_use_evaluate`) | assistant_project.md |
| 2026-04-11 12:53Z | Validation Guide Analysis — 78% implementation complete, 7 critical gaps identified | assistant_project.md |
| 2026-04-12 | Enhancement Implementation Plan completed (all phases 0-5) | assistant_project.md |
| 2026-04-16 | JSON-as-SSoT finalized (5 files); test suite restored to 427 pass / 9 skip / 2 xfail | assistant_project.md |
| 2026-04-17 16:43Z | Control plane (registry + jobs API + UI + tests) | assistant_project.md |
| 2026-04-17 20:00Z | Tutorial navigation (playbook + first-run tour) | assistant_project.md |
| 2026-04-17 20:21Z | Console encoding hardening (`SafeStreamHandler`) | assistant_project.md |
| 2026-04-18 | Agent design doc → AI Automation Agent full implementation | assistant_project.md (2 entries) |
| 2026-04-18 19:15Z | Agent + Expansion Engine + LLM Research Pipeline — all 3 implemented | assistant_project.md |
| 2026-04-20 01:29Z | Architecture diagram (HTML + Mermaid.js 5-tab) | assistant_project.md |
| 2026-04-22 | Codebase analysis: 230 actual Python files of 12,886 total | assistant_project.md |
| 2026-04-25 00:00IST | Documentation burst: ARCHITECTURE, CONVENTIONS, SCHEMAS, EXAMPLE_SERVICE, merged CLAUDE.md | assistant_project.md |
| 2026-04-25 00:30IST | 4 deeper references: CONFIG_REFERENCE, TESTING, AGENT_REFERENCE, GOVERNANCE | assistant_project.md |
| 2026-04-25 IST | 25 stale test files rewritten (Flow 4: executor, plan_compiler, tool_registry, evaluator, trainer, phase5_calibration, gaussian_update_pipeline) | assistant_project.md (6 entries) |
| 2026-04-26 | Backtest feature pipeline bug (3 compounding bugs) fixed | assistant_project.md |
| 2026-04-26 | Groq dependency removed (stdlib urllib) | assistant_project.md |
| 2026-04-26 | Unified Bridge — live metrics + execution audit columns | assistant_project.md |
| 2026-04-28 | Performance plan (8 bottlenecks, P1 implemented) | assistant_project.md |
| 2026-04-28 | Ultron disambiguation (3 objects, 6 files, zero dangling references) | assistant_project.md (2 entries) |
| 2026-04-28 | Dead code archive (6 files → archive/dead_code/) | assistant_project.md |
| 2026-04-29 | SIGNAL_FLOW.md created | assistant_project.md |
| 2026-04-29 | PromotionManager merge-into-base fix | assistant_project.md |
| 2026-04-30 | Sprint 1 (foundation) + Sprint 2 (S1/S10/S9/S2/S3) | assistant_project.md (2 entries) |
| 2026-04-30 | Sprint 3 (S4–S8) + Sprint 4 (StrategyOrchestrator + FusionEngine) | assistant_project.md (2 entries) |
| 2026-04-30 | RR data integrity audit (4 findings) | assistant_project.md |
| 2026-04-30 18:00Z | Sprint 5: MonteCarlo, KillSwitch, UATRunner (946 tests) | assistant_project.md |
| 2026-05-01 01:00Z | Sprint 6: Live hook integration (Telegram + MT5 + KS) (972 tests) | assistant_project.md |
| 2026-05-01 01:30Z | Sprint 7: Governance, Docker, HealthChecker, promote_v2.py (1001 tests) | assistant_project.md |
| 2026-05-02 | Integration Strategy: Unified Execution Spine (4 phases, 867 pass) | assistant_project.md |
| 2026-05-12 | Two-Layer Architecture: Pipeline A (Runtime) + Pipeline B (Research) | assistant_project.md |
| 2026-05-13 | Direction-mirroring discovery; v4_mirrored promoted (corr=+0.2066) | assistant_project.md (3 entries) |
| 2026-05-25 | Trade discovery tracing | assistant_project.md (6 entries) |
| 2026-05-27 07:55Z | Phase 0 Telemetry (true counts vs 23x wrong hypothesis) | assistant_project.md |
| 2026-05-27 08:30Z | Phase 1: Shadow Displacement Protection (8→93 EXPANSION) | assistant_project.md |
| 2026-05-27 12:20Z | Phase 2b: Score inversion diagnosis | assistant_project.md |
| 2026-05-27 15:26Z | Phase 4b: Shadow Age-Decay Gate implementation | assistant_project.md |
| 2026-05-28 00:00Z | Phase 4b results: shadow_advisory_only=true applied | assistant_project.md |
| 2026-05-28 01:00Z | Phase 3b expired counterfactual gate + Phase 5 plan | assistant_project.md |
| 2026-05-28 20:00Z | Architecture migration M0 docs + plan-persistence automation | assistant_project.md |
| 2026-06-06 19:45Z | Hidden Wiring Audit — 20 findings across Types A–G | assistant_project.md + reports/hidden_wiring_audit.md |
| 2026-06-06 20:22Z | Runtime Config Reachability Audit — Tier A findings (12 illusions) | assistant_project.md + reports/runtime_config_reachability.md |
| 2026-06-06 20:46Z | assistant_project.md ↔ CLAUDE.md bidirectional doc linking | assistant_project.md |
| 2026-06-09 | Edge Discovery M1 + M2; consensus sweep NULL; ROI/PF layer; session sweep | assistant_project.md (2 entries) |
| 2026-06-10 | M3 (deterministic HypothesisRunner); session OOS/G1: KEEP_INCUMBENT; session-override restored | assistant_project.md (2 entries) |

---

## Major Milestones

### 1. JSON-as-Single-Source-of-Truth (April 16)
Eliminated all hardcoded config defaults from Python source. Everything reads from `v1_multi_2026_03.json` via `from_prod_config()` classmethods that raise `KeyError` on missing keys. Made the system auditable — the question changed from "what value is actually used?" to "what does the config say?"

**Why it mattered:** Before this fix, there was no single place to audit configuration. A parameter could be overridden at the config file level, the Python default level, and the inline `.get(key, literal_default)` level — each with different values.

### 2. PlanCompiler Deterministic Layer (April 18)
The agent design was restructured after structural review to prevent the LLM from choosing tools or execution order. A hardcoded `PLAN_REGISTRY` maps intent_key → ordered `ToolStep[]`. The LLM can classify intent and fill arguments but cannot decide execution flow.

**Why it mattered:** Without this, the agent would have been an unpredictable black box. A hallucinated tool sequence could promote an untested config or toggle live trading.

### 3. PromotionManager Fix (April 29)
Sparse tuner entries (9 keys only) were being written as promoted configs. `get_prod_section("llama_gate")` on the new version would raise `RuntimeError`. The fix: deep-clone base config and overlay metadata.

**Why it mattered:** This was a near-miss. Without the fix, the next full config validation after promotion would crash — and the system would have been running with an incomplete config in the meantime.

### 4. Backtest Feature Pipeline Fix (April 26)
All feature columns were zero for an unknown period due to three compounding bugs (off-by-one + warmup offset, no error handling, column mismatch).

**Why it mattered:** This is a textbook example of how multiple independent errors can produce silent corruption. Any backtest results generated before the fix had zero feature data, making ML training on those results impossible.

### 5. Phase 0 Telemetry (May 27)
The discovery that actual EXPANSION episodes were 8 rather than the hypothesized ~184 (wrong by 23x) demonstrated that the system was being optimized against incorrect mental models.

**Why it mattered:** Three planned optimization candidates were INVALIDATED by the data. The entire optimization strategy pivoted from soft-conf tuning to shadow displacement protection. Without telemetry, the team would have continued optimizing the wrong levers.

### 6. Direction-Mirroring (May 13)
Identical feature vectors for long and short signals cancel signal during training. The fix (negate 10 directional features, swap 2 pairs) turned an unusable model (corr=+0.0062) into the active production model (corr=+0.2066).

**Why it mattered:** This was a fundamental ML insight about the data generation process. The scanner emits both directions per candle — without mirroring, the training signal is destroyed regardless of model quality.

### 7. Hidden Wiring Audits (June 6)
The discovery that 12 config keys are "illusions" — documented and defined but never read by code — and that `SCHEMAS.md` was systematically wrong about `fitness_weights` while the config was correct.

**Why it mattered:** This changed the team's understanding of which sources to trust. The documentation (SCHEMAS.md) was wrong; the code and config were correct. The "wrong configs promoted" risk was downgraded from CRITICAL to MEDIUM.

### 8. Session OOS/G1: KEEP_INCUMBENT (June 10)
The governance system correctly refused to promote +ASIA despite OOS robustness. +ASIA had retention 1.24, OOS expectancy +0.653R, and PF 3.25 — but failed G1's absolute floor (+0.48pp/month vs +1pp bar).

**Why it mattered:** This validated that the churn-prevention mechanism works. Refusing to promote a variant that is OOS-robust but falls below the absolute performance bar prevents unnecessary config churn.

### 9. Edge Discovery Determinism (June 10)
Byte-identical rerun proof: `always_long` run twice over 346,082 signals across 11 instruments into separate output directories produced identical `edge_report.json` (same sha256).

**Why it mattered:** Determinism is the foundation of scientific validity in trading research. Without it, you cannot distinguish signal from noise. This was prioritized over PF by explicit user directive: "REPRODUCIBILITY over PF (refused tuning)."

### 10. Backtest->Live Divergence Identified (June 6)
`ultron_gate_enabled: false` in the config creates systematic divergence: backtest at false produces inflated trade counts and win rates that do NOT reflect live behavior at true.

**Why it mattered:** Every backtest run with the current config produces results that cannot be reproduced in production. This is the single most dangerous issue identified in the audits.

---

## Architectural Evolution

### Original Architecture (pre-April 2026)
```
[CSV Input] → FeaturePipeline → [CRT Engine | Gaussian | Zone Gate | RR]
  → FusionEngine → DecisionEngine → ExecutionPlanner → UltronRiskGate → [Trade Record]
```
- Monolithic, file-backed
- Hardcoded config defaults scattered across Python
- Partial test coverage, no documentation
- Single production config (`v1_multi_2026_03.json`)
- CRT state machine: 8 states

### April 2026 — Foundation Layer
- Production config became single source of truth
- 8 companion docs created and cross-referenced in `CLAUDE.md`
- Test suite restored to full green (893+ passing)
- LLM dependency removed from Groq path
- Console encoding hardened for Windows cp1252

### Late April — Multi-Strategy Expansion
```
[10 Strategies S1-S10] → StrategyOrchestrator → EngineRunner context
  → [CRT | Gaussian | Zone Gate | RR] → FusionEngine (fuse_strategy_results)
    → DecisionEngine → ExecutionPlanner → UltronRiskGate → KillSwitch
      → TelegramAlert + MT5Order
```
- 10 strategies instead of single CRT-based
- HTTP Control Plane (port 8787) + HealthChecker (port 8788)
- Live bridges: Telegram, MT5
- Governance: ConfigValidator, PromotionManager, SHA-256, promotion_log
- Docker deployment
- Test suite: 1001 passing

### May — ML Pipeline + Two-Layer Architecture
```
Pipeline A (Runtime):   [CSV] → FeaturePipeline → [4 engines] → Fusion → Decision → Execute
Pipeline B (Research):  [CSV] → OpportunityScanner → Phase5 calibration → ModelRegistry
  → GaussianScorer (direction-aware, v4_mirrored, corr=+0.2066)
```
- Gaussian model went from unusable (corr=+0.0062) to production (corr=+0.2066)
- Direction-mirroring fixed ML cancellation
- Pipeline isolation prevents research from affecting production

### Late May — CRT State Machine Enhancement
```
8 states: RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION
9 states: RANGE → SWEEP → DISPLACEMENT → [SHADOW_PENDING] → EXPANSION → RETEST → EXECUTION
```
- SHADOW_PENDING state doubled expressiveness
- Shadow recovery: 18.2% of HTF displacement resets → new trades
- Age-decay gate: tunable λ from full inclusion to advisory-only
- TelemetryCollector: 5 event types, 2,649 records per run

### June — Edge Discovery Program (Parallel Research Platform)
```
[Hypothesis Plugin Layer] → CandleLoader → ForwardWalk → EdgeAggregator → EdgeReport
  [ @register_hypothesis expansion_breakout ]
  [ @register_hypothesis mean_reversion       ]
  [ control: random_baseline, always_long     ]
  → QualificationGate (M4: planned)
```
- Behavior-agnostic, isolation-guaranteed
- Deterministic by construction (byte-identical reruns)
- Cost model: 12 bps round-trip, NET qualification
- Research config (`research_config.json`) — no magic numbers in Python

### Architecture Migration Plan (Long-term North Star)
Goal: Event-driven LLM-event-microservices architecture.
- M0: Map & doctrine — COMPLETED
- M1: Telemetry normalization — NOT STARTED
- M2: Event extraction — NOT STARTED
- M3: Orchestration de-coupling — NOT STARTED
- M4: Dependency inversion — NOT STARTED
- M5: LLM-layer hardening — NOT STARTED

---

## Important Decisions

| Decision | Rationale | Alternatives Considered | Outcome |
|----------|-----------|------------------------|---------|
| **JSON as single source of truth** | Auditability, single change point | YAML, TOML, env vars, Python .py config | Adopted — all `.get(key, default)` eliminated |
| **PlanCompiler deterministic** | LLM cannot choose tools or order | Full LLM-driven planning with tool selection | Adopted — PLAN_REGISTRY hardcoded |
| **Shadow displacement protection** | HTF_CHANGE was 98.1% of resets; major lost opportunity | Ignore and tune other levers | Adopted — Phase 1, 18.2% recovery rate |
| **Shadow age-decay gate** | Shadow trades have worse RR than normal-path | Full inclusion or full exclusion | Adopted as configurable λ, `shadow_advisory_only` flag |
| **Direction-mirroring for short signals** | Combined long+short training cancels signal | Separate models per direction, more features | Adopted — v4_mirrored (corr=+0.2066) |
| **No promotion for +ASIA** | G1 absolute floor: +1pp/month | Relax threshold, promote anyway | Adopted — governance correctly refused churn |
| **Edge Discovery isolation** | Prevent research from affecting production | Same codebase with feature flags | Adopted — no `engine_runner`/`promotion_manager` imports |
| **Edge Discovery determinism before PF** | Distinguish signal from noise | Tune for PF first | Adopted — byte-identical rerun proof |
| **Advisory-only AI agent** | LLM must never execute trades | Full autonomy, human-in-the-loop | Adopted — confirm-gate + path-whitelist |
| **TelemetryCollector passive sidecar** | Zero behavior change | Inline logging in CRT engine | Adopted — ~200 lines, no control-flow change |
| **Groq via stdlib urllib** | Eliminate openai dependency | Keep SDK, switch to another provider | Adopted — `_groq_request()` pure urllib |
| **ConsoleSafeStreamHandler** | Windows cp1252 crashes on Unicode | Skip Unicode, encode to ascii | Adopted — `safe_print()` with fallback |
| **Ultron naming convention** | 3 objects with "Ultron" — each different role | Full rename all classes at once | Adopted — canonical names with backward-compat aliases |
| **INOUT archive (May 2)** | src/inout/ not wired in production path | Keep in src/ as dead code | Archived to `archive/inout_legacy/` |
| **Two-layer architecture** | Prevent research from contaminating runtime | Single pipeline with research mode | Adopted — Pipeline A + Pipeline B |

### Decisions That Were Rejected or Abandoned

| Rejected Idea | Reason | Date |
|---------------|--------|------|
| Full LLM-driven planning | Jarvis review: fundamental safety issue | 2026-04-18 |
| DynamoDB for feedback loop | Over-engineering for Phase 1; local JSONL preferred | 2026-04-18 |
| Soft-conf tuning as primary lever | Phase 0 telemetry: all decisions approved on candle 1, no near-misses | 2026-05-27 |
| `retest_depth_max` optimization | Phase 0 telemetry: ceiling not binding for any candidate | 2026-05-27 |
| +ASIA session promotion | OOS G1 absolute floor: +0.48pp < +1pp bar | 2026-06-10 |
| OFF_SESSION session ranges | OOS retention 0.19 (V2) and 0.59 (V3/V4) — did not survive | 2026-06-10 |
| `rr_fusion.enabled=true` | Requires rebuild of rr_dataset.json from canonical trades first | 2026-04-30 |

---

## Completed Work

### Core Trading Engine
- CRT state machine: 9 states (RANGE, SWEEP, DISPLACEMENT, SHADOW_PENDING, EXPANSION, RETEST, EXECUTION, RESOLVED, CANCELLED)
- 4 scoring engines: CRT (weighted sweep/breakout/retest/time formula), Gaussian (heuristic + ML variant via env var), Zone Gate (hard BitNet + soft distance/freshness/strength), RR (real distance-based)
- FusionEngine: weighted fusion + `fuse_strategy_results()` + regime-adaptive weights (configured but not active)
- DecisionEngine: with DynamicThreshold (percentile-85, clamped [0.45, 0.65])
- ExecutionPlannerV1_2: per-intent SL/TP/TTL
- UltronRiskGate: 7-check waterfall (disabled flag, TTL, RR floor, daily limit, kill switch, portfolio exposure, SL distance)
- RegimeGovernor (inside EngineRunner Step 6)
- TelemetryCollector: 5 event types, passive sidecar
- Shadow displacement protection: SHADOW_PENDING state + TTL
- Shadow age-decay gate: configurable λ, `shadow_advisory_only` flag

### Strategies & Orchestration
- 10 strategies (S1 CRT Wrapper, S2 Mean Reversion, S3 Breakout, S4 Stat Arb, S5 Grid, S6 Scalping, S7 News Sentiment, S8 ML Ensemble, S9 Pattern Recognition, S10 Trap)
- StrategyOrchestrator: completeness gate, consensus gate, weighted aggregation, per-strategy fail-open

### Training & ML Pipeline
- Opportunity scanner (long+short per candle, direction-mirroring)
- Phase5Calibration: 4 hard gates (min_val_samples, min_corr, max_cal_error, cv_stable)
- Train pipeline: validate_logs → build_dataset → train_gaussian → cross_val → calibration gate → register → promote
- v4_mirrored production model: corr=+0.2066, CV stable (std=0.0072), 242K samples
- ModelRegistry: GaussianScorer (direction-aware mirroring), NoOpScorer

### Backtesting
- BacktestRunner: CSV input, feature pipeline, multi-instrument, per-trade audit (8 live metric columns)
- Performance optimizations: P1 (skip_features), timestamp cache, precomputed lookups
- Unified Bridge: live-at-entry metrics alongside batch features

### Governance
- ConfigValidator: 3 hard gates (min 10 trades, max 35% DD, min fitness 0.15), soft gates, automation mode
- PromotionManager: promote_from_report, promote_from_tuner_checkpoint, promote_direct, merge-into-base
- MultiStrategyValidator: 3 hard gates across instruments
- ShadowPromotionGate: sample-size gate + strict performance gate
- MetaGovernorExecutor: LLM inference + config validation + governance event logging
- PortfolioValidation: 8 instruments, PortfolioAnalytics aggregate
- Rollback procedure: 6 steps
- `promotion_log.jsonl`: append-only PROMOTED/PROMOTION_FAILED events

### Live Trading Infrastructure
- TelegramBridge: signal alerts, kill switch alerts, daily summary
- MT5Bridge: order placement, position closing, account info
- KillSwitch: JSON-persisted daily/weekly loss gate with date rollover
- HealthChecker: stdlib HTTP on port 8788, daemon thread
- live_engine_hook: StrategyOrchestrator, KillSwitch pre-check, Telegram alerts, MT5 orders

### AI Agent
- IntentRouter: regex + LLM classification, 14 intents, confidence floor 0.6
- PlanCompiler: deterministic PLAN_REGISTRY, 17 tools across 3 modes
- Executor: confirm-gate + path-guard whitelist
- Audit: per-step tool_call/outcome/error records + per-session intent/metrics summary
- REPL CLI: pipeline/copilot/governance modes
- Prompts: system_copilot, system_governance, intent_router, tool_schema

### Control Plane
- Typed CommandSpec registry with categories and argv templates
- Threaded JobManager with async execution
- HTTP API (CRUD commands + job lifecycle)
- Browser UI with dashboard, job detail, console, help panels
- Tutorial system: playbook + first-run guided tour (localStorage persistence)
- CLI matrix auto-generation

### Monitoring
- HealthChecker: HTTP on port 8788, `/health` and `/status` endpoints
- FeatureMonitor: wired into BacktestRunner, HARD/SOFT drift detection
- ConsoleSafeHandler: Unicode-safe logging for Windows cp1252

### Testing
- ~1000+ tests across 10 domains
- Coverage: engines, config_layer, core, governance, agent, expansion, external I/O
- Test patterns: structured-return assertion, invariant precondition, parametrised, registry exhaustiveness
- Conventions enforced: tool registration, write-flag gating, PLAN_REGISTRY non-empty, JSONL field presence, schema stability, cp1252 safety, control-plane doc↔code alignment

### Documentation
- 15+ docs across 4 tiers (root, docs/, docs/architecture/, docs/analysis/)
- All cross-referenced via `CLAUDE.md` §2 companion-docs table
- Authoritative-source rules: config=true in JSON, flow=SIGNAL_FLOW.md, events=EVENT_TAXONOMY.md
- Architecture migration doctrine: M0 (mapping docs) completed

### Infrastructure
- Dockerfile (Python 3.10-slim, EXPOSE 8787/8788)
- Plan-persistence automation (PostToolUse hook, Powershell)
- Git repo with 9b231f51 hash as of June 10

---

## Deferred or Unfinished Work

### 1. Architecture Migration M1–M5
**What's missing:** No code changes for envelope trade writers (M1), event extraction (M2), orchestration de-coupling (M3), dependency inversion (M4), or LLM-layer hardening (M5).
**Why postponed:** M0 mapping docs were completed on May 28. M1–M5 code changes were never started. No explicit reason recorded — the team pivoted to Edge Discovery Program instead.
**Dependencies:** M0 documents serve as the specification. M1 needs trade_logger.py + sweep_trace_logger.py enveloping.

### 2. Phase 5a/5b (Selectivity Sweep + Reject Audit)
**What's missing:** Phase 5a threshold sweep (`tier_2_threshold = [0.44..0.60]`) and Phase 5b reject audit (simulate `outcome_if_taken` for LOW_SCORE rejects) were never executed.
**Why postponed:** Phase 4b results (shadow_advisory_only=true) and Phase 5 plan were documented on May 28, but the sweeps and audits were deferred to focus on Edge Discovery.
**Dependencies:** Backtest infrastructure; 7 runs for Phase 5a.

### 3. Phase 5c Telemetry Code Changes
**What's missing:** Code changes planned: rename `_age` → `_cross_window_distance`, add `approval_path`/`context_source`/`decision_distance` to `CANDIDATE_LIFECYCLE`, add `_htf_transition_distance` to EngineState.
**Why postponed:** Same as Phase 5a/b — documented but not prioritized over Edge Discovery.
**Status:** Plan document exists with exact field names and behavior.

### 4. Edge Discovery M4+
**What's missing:** M4 (QualificationGate: NET hard rejects, IS/OOS split, bootstrap CI + permutation test, Benjamini-Hochberg correction, verdict PROMOTE/REJECT/INSUFFICIENT), M4.5 (meta-analysis), M4.7 (economic-explanation gate), M5 (full 17-instrument sweep), M6 (cross-validation against L1 ETF, L2 sector, L3 macro), M7 (Monte Carlo stress), M8 (live paper trading), M9 (autonomous loop), M10 (monitoring + auto-demotion).
**Why postponed:** M3 shipped on June 10. Next step (M4) was documented but not yet started.
**Dependencies:** M3 runner + research_config.json.

### 5. FeatureStore Live Ingestion Boundary
**What's missing:** Identified as a gap on April 28 during the dead code archive pass. FeatureStore wiring as live ingestion boundary was proposed but never implemented.
**Why postponed:** Followed P1 (performance) and Ultron disambiguation priorities.

### 6. regime_factors in Production Config
**What's missing:** `regime_factors` dict (trend=1.0, range=0.8, neutral=0.6, uncertain=0.5) hardcoded in `UltronRiskGateWrapper` defaults. Not in production config.
**Why postponed:** UltronRiskGateWrapper is orphan (not wired in production). Fixing the config is blocked on wiring the wrapper.

### 7. Six Dead Files — `git rm` Not Executed
**What's missing:** 6 files copied to `archive/dead_code/` on April 28. `git rm` of `src/` originals was documented as next step but not executed.
**Files involved:** `src/bitnet/_smoke_test.py`, `src/features/bitnet_feature_builder.py`, `src/ui/dashboard.py`, `src/config_layer/insight_reporter.py`, `src/journal/trade_logger.py`, `src/journal/schema.py`.
**Status:** `src/journal/__init__.py` intentionally left (user rejected deletion).

### 8. TP3 / frequency_boost
**What's missing:** Mentioned as pre-existing failures in the test suite. 2 failures in `tests/` for TP3 and frequency_boost features.
**Status:** Out of scope for Sprint work. Pre-existing, not introduced by any tracked change.

### 9. live_integration Config Section
**What's missing:** `v2_multi_2026_04.json` missing `live_integration` section → `MT5Bridge.from_prod_config()` and `TelegramBridge.from_prod_config()` fail. Causes 2 failures + 5 errors in test suite.
**Status:** Identified as pre-existing known issue (not introduced by Sprint work). Confirmation to add was requested from user but not explicitly confirmed.

### 10. UltronRiskGateWrapper (Orphan)
**What's missing:** Pre-scaling utility exists at `src/core/ultron_risk_gate_wrapper.py` but is NOT wired in any production path. Regime-based pre-scaling of `risk_percent` before delegation to `UltronRiskGate`.
**Status:** Documented as orphan during Ultron disambiguation (April 28).

### 11. INOUT Archive Verification
**What's missing:** Confirmation that archived INOUT code is not still active via a different deployment path (e.g., separate process loading from `archive/inout_legacy/`). Noted as open question during June 6 audits.
**Status:** Open — out of scope for audit.

### 12. SPRINT_TRACKER.xlsx
**What's missing:** Jira-standard 3-sheet tracker (Dashboard/Backlog/Open Items). xlsx skill was invoked on April 30 but did not complete. Multiple attempts failed.
**Status:** Pending — requires xlsx package or manual creation.

### 13. Baseline Capture + Full Validation Flow
**What's missing:** `python runtime/baseline_capture.py --label phase0` listed as next step after enhancement plan completion. `ConfigValidator.validate-prod` end-to-end promotion gate run also listed.
**Status:** Documented as next steps but no evidence of execution in session log.

### 14. RR Dataset Rebuild
**What's missing:** `models/rr_dataset.json` is degenerate (all zeros, wrong schema). Needs rebuild from canonical trade records before `rr_fusion.enabled=true` can be wired.
**Why postponed:** Quarantine was recommended, rebuild depends on real canonical trade records being available.

### 15. `regime_fusion_weights` Wiring
**What's missing:** 4×5 regime weight matrix exists in config (`regime_fusion_weights.TRENDING/RANGING/VOLATILE/UNKNOWN`) but `FusionConfig` constructor in `engine_runner.py:374-390` only reads flat weights. CONFIG_REFERENCE.md doesn't document the regime block.
**Status:** 70% confidence that regime-adaptive weights are not applied. Identified in hidden wiring audit Finding #6.

### 16. Direction Threading from CRT Signal (engine_runner)
**What's missing:** `engine_runner.py` gaussian path uses `HeuristicGaussianEngine` by default (no direction threading). `MLGaussianEngine` (`GAUSSIAN_IMPL=ml` path) supports direction but is not default. `live_engine_hook.py` direction threading exists (line 640-645) but confirmed May 13.
**Status:** `HeuristicGaussianEngine` is direction-agnostic (returns same score for long and short). Direction threading works for ML path only. Default path remains direction-blind.

---

## Current State of the Project (June 10, 2026)

### System Status
- **Production config:** `v2_multi_2026_04 - deepdeektry.json`
- **Active model:** `v4_mirrored` (corr=+0.2066, direction-aware, 242K samples)
- **Test suite:** ~1000+ passing, 47 known pre-existing failures (TP3/frequency_boost/llm/promotion)
- **Audit state:** Local, file-backed. No database, no message broker, no cloud dependencies.
- **Promotion mechanism:** ConfigValidator → PromotionManager → SHA-256 + promotion_log.jsonl
- **Rollback:** Copy not move, update PROD_VERSION, append ROLLBACK to log, smoke-test

### Active Tracks
1. **CRT Pipeline Improvement** — Shadow displacement protection is live. Phase 5 selectivity tuning (threshold sweep, reject audit, telemetry additions) is planned but not started.
2. **Edge Discovery Program** — M3 shipped on June 10. M4 (QualificationGate) is next.
3. **Architecture Migration** — M0 completed on May 28. M1–M5 not started.

### What's Blocking Go-Live
1. **Missing `live_integration` config section** — Telegram and MT5 bridges fail on `from_prod_config()`.
2. **Backtest-vs-live divergence** — `ultron_gate_enabled: false` inflates backtest results. Results do not reflect live behavior.
3. **Direction blindness in default Gaussian path** — `HeuristicGaussianEngine` is direction-agnostic. ML path with direction threading is not default.

### What's Green
- 10 strategies, orchestrator, fusion engine — verified
- Governance chain (validate → approve → promote → backtest) — verified end-to-end
- Edge Discovery M0-M3 — deterministic, isolation-guaranteed, verified
- CRT state machine with SHADOW_PENDING — verified, production config active
- 1001 tests passing through Sprint 7
- Documentation: 15+ docs, self-consistent, cross-referenced

### What's Fragile
- `SCHEMAS.md` drifts from actual code (fitness_weights keys wrong)
- `CONFIG_REFERENCE.md` was generated from `v1_multi_2026_03` — differences from `v2_multi_2026_04` not tracked
- 12 H-class config illusions (keys that appear tunable but have zero effect)
- INOUT code archived but not verified inactive via alternative deployment
- `python -m research.cli` requires `PYTHONPATH=src` (not an installed console_script)

---

## Config Illusions Register

These are config keys documented in `configs/production/v2_multi_2026_04.json` that appear tunable but have **zero runtime effect**. Source: `reports/runtime_config_reachability.md` (Tier A confirmed) and `reports/hidden_wiring_audit.md`.

| # | Config Key | Value | Illusion Type | Why It's Dead | Confidence |
|---|-----------|-------|---------------|---------------|------------|
| 1 | `capital_management.*` (10 keys) | 50,000 INR etc. | H (Dead Config) | Zero consumers. Capital protection uses `ultron_risk_gate`. | HIGH |
| 2 | `data_ingestion.*` (5 keys) | postgresql://localhost | H (Dead Config) | No database in this system. All state is file-backed. | HIGH |
| 3 | `gate_intelligence.*` (5 keys) | weights + 0.55 threshold | H (Dead Config) | No consumer in spine (EngineRunner → Fusion → Decision → Execution). | HIGH |
| 4 | `sl_tp_comparison.*` (6 keys) | legacy SL/TP values | H (Self-declared dead) | Config's own `_comment` says "Used ONLY by SLTPComparator, never in live path." | 100% |
| 5 | `signal_belief.*` | (various) | H (Dead Config) | No consumer found in any engine or gate. | MEDIUM |
| 6 | `cognitive_layer.*` | (various) | H (Dead Config) | No consumer found. Module may not exist. | MEDIUM |
| 7 | `phase5_calibration.min_val_samples` | 30 | H (Dead Config) | Phase5Calibration now reads from training section, not top-level. | MEDIUM |
| 8 | `decision_engine.score_threshold` | 0.45 | H (Illusion) | Stored but NEVER read. Effective threshold = DynamicThreshold percentile-85 [0.45, 0.65]. | HIGH |
| 9 | `fusion_engine.weight_crt/gaussian/zone_gate/rr` | 0.4/0.2/0.2/0.2 | H (Shadow Override) | `regime_fusion_weights` block exists in config with different values, but FusionConfig only reads flat weights. | 70% |
| 10 | `ultron_gate_enabled: false` | false | H (Split Brain) | Backtest at false ≠ live at true. Inflates trade counts and win rates in backtest only. | HIGH |
| 11 | `PROMOTION_MARGIN` | 2% | C (Hardcoded) | Not configurable — `model_registry.py` hardcodes 2%. No config key exists. | HIGH |
| 12 | `execution_planner.min_rr_ratio` | (not in config) | H (Documentation error) | CONFIG_REFERENCE.md says ExecutionPlanner reads these. Source read confirms: SL/TP/RR delegated to gate_intelligence. | HIGH |

**Total: 12 confirmed illusions.** 8 of these are actionable (can be deleted or wired). 4 require code changes to activate.

---

## Missing Information

1. **Pre-April 2026 history is not captured.** The core CRT engine, state machine, and initial `v1_multi_2026_03` config existed before the session log began. No documents from this period were found.

2. **Several early April entries lack precise timestamps** (day only, no hour/minute). These are marked with `??` in the session log: April 10 entries at 17:37Z and 18:25Z, April 11 entry at 13:00:58+05:30.

3. **The exact date when the test suite was first established** is not recorded. By April 10, tests already existed and were being fixed.

4. **No SPRINT_TRACKER.xlsx was ever verified as created.** The xlsx skill failed on multiple attempts (April 30). No evidence of manual creation.

5. **Whether INOUT archive is active via alternative deployment** remains unverified. The files were archived on May 2 but no confirmation check was performed.

6. **The session log file `assistant_project.md` was accidentally truncated** at some point (reported on May 25: "Detected accidental truncation of assistant_project.md during session-log appends"). It was restored from repository content. There is a small risk some entries between the truncation and restoration were lost.

7. **`live_integration` config section fix** was documented as requiring user confirmation but no explicit confirmation was recorded.

8. **File creation dates** were not used for any claims in this document because all events have session-log timestamps.

---

## Supporting Evidence Reference

Every claim in this document can be traced to one of these sources:

| Evidence Source | Location | Coverage |
|----------------|----------|----------|
| Session Log | `assistant_project.md` (1946 lines) | All entries from April 10 to June 10, 2026 |
| Companion Docs | `docs/` (9 files) | Architecture, conventions, schemas, config, testing, agent, governance, signal flow, CLI |
| Architecture Docs | `docs/architecture/` (7 files) | Goal, event taxonomy, codebase map, service boundaries, replay governance, LLM layer, trigger vocabulary |
| Hidden Wiring Audit | `reports/hidden_wiring_audit.md` (339 lines) | 20 findings Types A–G with per-finding confidence |
| Runtime Config Reachability | `reports/runtime_config_reachability.md` (615 lines) | Tier A source-confirmed findings, H-class illusion register |
| Operating Manual | `CLAUDE.md` (251 lines) | Companion doc map, 7-step feature pattern, constraints |
| README | `README.md` (112 lines) | Quick Start, 4-tier docs map, authoritative-source rules |

---

*Generated from source: `assistant_project.md` (1946 lines), `reports/hidden_wiring_audit.md` (20 findings), `reports/runtime_config_reachability.md` (Tier A classifications), `CLAUDE.md`, `README.md`, and all companion docs created April 25, 2026. Last event captured: June 10, 2026, 12:45 AM IST. Timestamps derived from session log entries; file metadata used only where explicitly noted.*