# Existing Architecture → Framework Mapping

> **Purpose:** Specific, one-to-one mapping between every existing codebase component and
> the 6-level framework hierarchy. Shows exactly where each piece lives in the new system,
> and what changes (if any) are needed.
>
> **Use this to:** Guide implementation. Every existing component has a target location.
> Every new component has a design requirement from existing intent docs.

> ⚠️ **Reconciliation (2026-06-16, post Framework-Registry build) — CLAUDE.md §6.2.** Several
> status claims below were code-verified against the registry and found to be **DOC_DRIFT**. The
> machine-readable, evidence-anchored truth is now [`data/framework_registry.jsonl`](../../data/framework_registry.jsonl)
> (authoritative on conflict); see [`reports/framework_gap_audit.md`](../../reports/framework_gap_audit.md).
> Corrected below but kept for history:
> - **Lines 154/161/167/250/274 — "UltronRiskGate DISABLED / enable `ultron_gate_enabled: true`":**
>   FALSE. `disabled=false` in the active config (`v2_multi_2026_04.json`) and the gate is wired in
>   `src/runtime/live_engine_hook.py`. It is **ENABLED and live** (registry `RISK-001` = `extant`).
> - **Line 181 — `src/inout/executor.py` (order-dispatch stub):** that path **does not exist**; the
>   live execution surface is `src/engines/live_engine.py` (registry `EXEC-002` = `stub`, F-010).
> - **Line 157/168 — wire `capital_management` into UltronRiskGate:** the modules exist but are
>   orphaned (registry `RISK-002` = `orphaned`, F-013); the "into UltronRiskGate" wiring is aspirational.

---

## Level 0: Universal Trading Kernel

**Existing code that maps here (mostly unchanged):**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `src/features/feature_pipeline.py` | Feature pipeline | None — domain-agnostic. Move to `src/kernel/feature_pipeline.py` (optional) |
| `src/features/feature_monitor.py` | Drift detector | Wire drift actions (Story 8.3). Currently F-008: detected but not acted on. |
| `src/runtime/backtest_v2.py` | Backtest runner | Add `domain_tag` to Trade schema. Currently missing domain context. |
| `src/core/collector.py` | Audit logger | Add `strategy_tag`, `style_tag`, `domain_tag` to every record. |
| `src/utils/` | Logging utilities | None |
| `src/config_layer/production_config.py` | Config loader | None |
| `configs/production/*.json` | Config files | Add new sections for domain/style/strategy. |

**Existing intent docs that govern this level:**
- `docs/intent/100_execution.md` §Must: "All 4 engines must score every candle" → **This changes to style-scoped.**
- `docs/intent/100_execution.md` §Must Never: "Must NEVER allow lookahead in backtest" → **Preserved.**
- `docs/intent/200_risk.md` §Pre-Trade: "Max daily loss, drawdown limits" → **Preserved, enhanced.**

**What's NEW in this level (not in codebase):**
- `src/kernel/` package (or keep in `src/core/`) — purely organizational
- Formal `Candle` dataclass (currently implicit dict)
- Formal `Trade` schema with `domain_tag`, `strategy_tag`, `style_tag`

---

## Level 1: Market Domain Layer

**Existing code that maps here:**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `scripts/data/fetch_crypto_ccxt.py` | CryptoSpot data source | Create `CryptoSpotDomain` class extracting its assumptions |
| `scripts/data/fetch_candles_hummingbot.py` | CryptoSpot alternate source | Same domain class |
| `scripts/data/fetch_forex_yfinance.py` | Forex data source (dormant) | Create `ForexDomain` class |
| `scripts/data/fetch_candles_alphavantage.py` | FX data source (dormant) | Same domain class as Forex |
| `configs/production/*.json` session_calendar | Implicit domain config | Extract into `CryptoSpotDomain.calendar()` |
| `configs/production/*.json` cost model (implicit 12bps) | Implicit cost model | Extract into `CryptoSpotDomain.cost_model()` |

**Existing intent docs that govern this level:**
- `docs/intent/100_execution.md` — Currently assumes single domain. Will be scoped per-domain.
- `docs/intent/900_preservation.md` — "Code longevity, migration strategy" — Domain layer serves this.

**What's NEW:**
- `src/domain/base.py` — `TradingDomain(ABC)` abstract base class
- `src/domain/crypto_spot.py` — First concrete implementation
- `src/domain/forex.py` — Second concrete implementation (can be built later)
- `src/domain/crypto_futures.py`, `equities.py`, `futures.py`, `options.py` — Stubs (planned)

---

## Level 2: Trading Style Layer

**Existing code that maps here:**

| Existing Module | Style | Changes Needed |
|----------------|-------|---------------|
| `src/strategies/s01_crt_wrapper.py` | ReactionBased | Group under ReactionBased style. CRT is a strategy, not an engine. |
| `src/strategies/s10_trap_strategy.py` | ReactionBased | Same style as CRT. Both are reaction-based. |
| `src/strategies/s07_news_sentiment.py` | ReactionBased | Same style. |
| `src/strategies/s02_mean_reversion.py` | MeanReversion | Group under MeanReversion style |
| `src/strategies/s04_stat_arb.py` | MeanReversion | Same style |
| `src/strategies/s03_breakout.py` | Breakout | Group under Breakout style |
| `src/strategies/s06_scalping.py` | Momentum | Group under Momentum style |
| `src/strategies/s05_grid.py` | Grid | Group under Grid style |
| `src/strategies/s09_pattern_recog.py` | Pattern | Group under Pattern style |
| `src/strategies/s08_ml_ensemble.py` | ML/Hybrid | Group under ML/Hybrid style |
| *(new)* | TrendFollowing | NEW — MA Cross strategy (S11) |

**Existing intent docs that govern this level:**
- `docs/STRATEGIES.md` — Currently lists strategies flat. Needs style grouping.
- `docs/intent/100_execution.md` §Must: "All 4 engines must score every candle" → **Replaced by style-scoped engine check.**

**What's NEW:**
- `src/styles/base.py` — `TradingStyle(ABC)` abstract base class
- `src/styles/reaction_based.py` — Groups CRT, LiquiditySweep, NewsSentiment
- `src/styles/mean_reversion.py` — Groups RSI+BB, StatArb
- `src/styles/breakout.py` — Groups BOS+Volume
- `src/styles/momentum.py` — Groups MACD (scalping)
- `src/styles/grid.py` — Groups ATRGrid
- `src/styles/pattern.py` — Groups Candlestick
- `src/styles/ml_hybrid.py` — Groups ML Ensemble
- `src/styles/trend_following.py` — NEW (MA Cross)

---

## Level 3: Strategy Layer

**Existing code that maps here (largely unchanged):**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `src/strategies/s01_crt_wrapper.py` | CRT strategy | No logic change. Registry marks parent=ReactionBased style. |
| `src/strategies/s02_mean_reversion.py` | RSI+BB strategy | No logic change. Registry parent=MeanReversion. |
| `src/strategies/s03_breakout.py` | BOS+Volume strategy | No logic change. Registry parent=Breakout. |
| `src/strategies/s04_stat_arb.py` | StatArb strategy | No logic change. Registry parent=MeanReversion. |
| `src/strategies/s05_grid.py` | ATR Grid strategy | No logic change. Registry parent=Grid. |
| `src/strategies/s06_scalping.py` | MACD strategy | No logic change. Registry parent=Momentum. |
| `src/strategies/s07_news_sentiment.py` | News strategy | No logic change. Registry parent=ReactionBased. |
| `src/strategies/s08_ml_ensemble.py` | ML Ensemble strategy | No logic change. Registry parent=ML/Hybrid. |
| `src/strategies/s09_pattern_recog.py` | Candlestick strategy | No logic change. Registry parent=Pattern. |
| `src/strategies/s10_trap_strategy.py` | LiquiditySweep strategy | No logic change. Registry parent=ReactionBased. |

**Critical change: CRT is no longer a mandatory engine.**
- `EXPECTED_ENGINES` in `engine_runner.py` no longer requires "crt"
- CRT runs only when ReactionBased style is active
- CRT's weight is 0.3 (reduced by F-026 finding)

**What's NEW:**
- `src/strategies/s11_ma_cross.py` — MA Cross strategy (enabled: false by default)

---

## Level 4: Intelligence / AI Layer

**Existing code that maps here:**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `src/bitnet/bitnet_inference.py` | BitNet hard-reject gate | Keep. Already advisory (F-004 confirmed: live at 0.55). |
| `src/engines/llm_engine.py` | LLM advisory scorer | Fix fallback contract (Story 1.1). Currently 0.5 vs 1.0 ambiguity. |
| `src/cognitive/` | Regime classifier | ORPHANED (F-012). Needs wiring to determine which styles get capital. |
| `src/features/feature_monitor.py` | Drift detector | Wire actions (Story 8.3). |
| `src/agent/` | AI automation agent | Keep. Determines PLAN_REGISTRY tools. |

**Existing intent docs that govern this level:**
- `docs/intent/500_agent.md` — Agent contract. "LLM is NOT involved in planning — pure Python dispatch."
- `docs/intent/100_execution.md` §Must Never: "Must NEVER allow the LLM to approve or reject a trade — advisory only, observed only."

**What's NEW:**
- Wire `src/cognitive/` regime classifier into EngineRunner (currently isolated)
- Wire drift detection → action (Story 8.3)
- Add `src/governance/findings_applier.py` — AI layer doesn't make decisions, but findings do drive weight adjustments

---

## Level 5: Risk Layer

**Existing code that maps here:**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `src/core/ultron_risk_gate.py` | PreTradeRiskGate | ENABLE it (ultron_gate_enabled: true). Currently DISABLED. |
| `src/config_layer/execution_planner.py` | InTradeRisk (SL/TP/TTL) | Already active. Add SL floor = 2x ATR (F-025). |
| `src/portfolio/` | PortfolioRisk | ORPHANED (F-013). Wire into spine. |
| `configs/production/*.json` capital_management | Risk config | UNWIRED (hidden_wiring_audit #1). Wire into UltronRiskGate. |

**Existing intent docs that govern this level:**
- `docs/intent/200_risk.md` — Complete risk contract: pre-trade, in-trade, portfolio.
  - §Pre-Trade: Max daily loss, max drawdown, kill switch → **EXISTS but DISABLED**
  - §In-Trade: Breakeven, trailing, partial TP → **ACTIVE (in ExecutionPlanner)**
  - §Portfolio: Correlation, exposure → **ORPHANED (portfolio module not wired)**
  - §LLM Constraint: "LLM must never approve/place a trade" → **PRESERVED**

**What's NEW:**
- `ultron_gate_enabled: true` (1 line change)
- Wire `capital_management` config section into UltronRiskGate (Story 2.1)
- Wire `src/portfolio/` into spine (Story 8.2)
- Add SL floor = 2x ATR minimum (F-025 directive)

---

## Level 6: Execution Layer

**Existing code that maps here:**

| Existing Module | Framework Role | Changes Needed |
|----------------|---------------|----------------|
| `src/config_layer/execution_planner.py` | Execution planner | Add domain-parameterized SL/TP (currently fixed). |
| `src/inout/executor.py` | Order dispatch | STUB (live path not verified, F-010). Needs testing. |
| `configs/production/*.json` execution_planner | Execution config | Add per-domain overrides. |

**Existing intent docs that govern this level:**
- `docs/intent/100_execution.md` §Must: "ExecutionPlanner must produce entry/SL/TP/RR/TTL for ACCEPTED decisions" → **PRESERVED.**
- `docs/intent/200_risk.md` — Execution quality monitoring → **NOT YET IMPLEMENTED (F-010).**

**What's NEW:**
- Slippage model: dynamic (spread-based), not fixed 12bps (Story 8.2 in spirit)
- Fill simulation for backtest: volume-dependent impact, not fixed
- Venue routing: single exchange only for now (Binance)

---

## Cross-Cutting: Intent Docs → Registry

Every existing intent doc becomes a **registry record** with `type=intent`:

| Intent Doc | Registry ID | Links to (children) |
|------------|-------------|-------------------|
| `docs/intent/000_governance.md` | INTENT-000 | `GOV-001` (promotion_manager), `KERNEL-006` (collector) |
| `docs/intent/100_execution.md` | INTENT-100 | `KERNEL-001` through `KERNEL-006`, `STYLE-001` through `STYLE-007` |
| `docs/intent/200_risk.md` | INTENT-200 | `RISK-001` (ultron_risk_gate), `EXEC-001` (execution_planner), `PORT-001` (portfolio) |
| `docs/intent/300_memory.md` | INTENT-300 | `AI-XXX` (agent), `KERNEL-006` (collector) |
| `docs/intent/400_research.md` | INTENT-400 | `KERNEL-005` (backtest), findings F-001 through F-029 |
| `docs/intent/500_agent.md` | INTENT-500 | `AI-001` (agent package), plan_compiler, tool_registry |
| `docs/intent/900_preservation.md` | INTENT-900 | All components — meta-intent |

Each intent doc's **Must/MustNever** requirements become validation rules in the registry.

---

## Cross-Cutting: Findings → Registry

Every finding (F-001 to F-029) becomes part of registry records:

| Finding | Affected Component | Action |
|---------|-------------------|--------|
| F-001 | All kernel components | Informational: "intelligence not the binding constraint" |
| F-004 | AI-002 (BitNet) | Confirm: BitNet live at 0.55 threshold |
| F-005 | AI-XXX (TradeNet v2) | Status = orphaned |
| F-006 | GOV-001 (config_integrity) | Status = orphaned → wire or remove |
| F-008 | KERNEL-004 (feature_monitor) | Wire drift → action |
| F-010 | EXEC-002 (live executor) | Status = stub, not verified |
| F-012 | AI-003 (cognitive), IMPL-006 (replay) | Status = sidecar (not spine) |
| F-013 | PORT-001 (portfolio) | Status = orphaned → wire |
| F-016 | Domain config | Version truth: active = v2_multi_2026_04 |
| F-019 | DOMAIN-001 (CryptoSpot) | No edge on crypto majors |
| F-021 | STRAT-001 (CRT), STYLE-001 (ReactionBased) | Sessions only, score/zone non-binding |
| F-025 | RISK-001 (risk gate), EXEC-001 (exec planner) | Exit is risk lever, not expectancy |
| F-026 | STRAT-001 (CRT) | CRT retest adds no edge → deweight to 0.3 |

---

## Summary: What Stays vs What Changes

| Aspect | Stays (no change) | Minor Change | Major Change (feature flagged) |
|--------|-------------------|-------------|-------------------------------|
| **Code modules** | 30+ modules (all strategies, engines, core) | Add `--workdir` flag to 5 scripts | Style-scoped engine check (Story 5.4) |
| **Config** | 90% of config values | Add 3 new sections (capital_management wiring) | style_scoped_engines flag |
| **Tests** | 1188 passing tests | Fix 23 failing tests | None — all new tests are additive |
| **Findings** | 29 findings | Link to registry records | Findings applier module (new code) |
| **Intent docs** | 7 intent contracts | Add evidence links to registry | None |
| **Risk gate** | Code exists | ENABLE it (1 line) | Portfolio wiring |
| **n8n** | Doesn't exist yet | Docker Compose + webhooks | Entirely new orchestration layer |
| **Claude gate** | Doesn't exist yet | 3 prompt templates + handler | Entirely new LLM integration |

**The architecture does not break. It extends.** Every existing module continues to work.
New behavior is added behind feature flags defaulting to `false`. The only non-flagged
change is enabling UltronRiskGate (Story 8.1) — which is the highest risk and deserves
extra caution.

---

## Implementation Order (Specific to Existing Architecture)

### Phase 0: Registry first (measure before change)
1. Story 3.1: Build registry module + schema
2. Story 3.2: Seed registry with all existing components
3. Story 3.3: CLI query tool
4. **Result:** Can query "what exists" at any time

### Phase 1: Fix what's broken (repair trust)
5. Story 1.1-1.6: Fix 23 failing tests
6. **Result:** Codebase trustworthy

### Phase 2: Wire findings to registry (connect evidence)
7. Story 3.5: Findings applier module
8. Story 10.2: Link all 29 findings to components
9. **Result:** Findings drive behavior, not just docs

### Phase 3: Enable risk (protect capital)
10. Story 2.1: Wire capital_management into risk gate
11. Story 8.1: Enable UltronRiskGate
12. **Result:** Capital protected

### Phase 4: Extract domain (architectural correct)
13. Story 4.1: Domain ABC
14. Story 4.2: CryptoSpotDomain
15. Story 5.1-5.2: Style ABC + classify strategies
16. Story 5.4: Style-scoped engines (HIGH RISK, behind flag)
17. **Result:** Architecture is now domain-first

### Phase 5: Automate (operational efficiency)
18. Story 6.1-6.4: n8n Docker + webhooks + workflow
19. Story 7.1-7.2: Claude gate handler + prompts
20. **Result:** Full pipeline automated

---

**This mapping ensures that every existing piece of code, every intent doc, every finding,
and every config key has a specific destination in the framework. Nothing is lost.**