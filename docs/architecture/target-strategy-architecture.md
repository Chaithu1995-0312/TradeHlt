# Target Strategy Architecture

> **What this is.** The **city plan** for evolving Tradelatest without violating the North Star.
> Freezes **strategy vs market semantics**, config authority, research/live separation, BitNet’s role,
> Strategy Registry, decision ledger, and the **Strategy Lifecycle** that ties research to production.
> Distinguishes **target architecture** from **current implementation**. **No code / promotion authority.**
>
> **Created:** 2026-07-28 · **Updated:** 2026-07-28 (lifecycle + goal.md pairing) ·
> **Status:** TARGET + checklist (not a promotion grant)
>
> **Companions:** [`goal.md`](goal.md) (**constitution** / north star) · [`signal-flow.md`](signal-flow.md) (live path) ·
> [`docs/governance/config_authority_matrix.md`](../governance/config_authority_matrix.md) (WHO/HOW/WHAT fields) ·
> [`docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md`](../governance/MODEL_INTENT_AUTHORITY_REGISTER.md) (MIAR) ·
> [`docs/intent/`](../intent/) (domain contracts) · CLAUDE.md §6.5 (Config-First + Authority Ladder)

---

## 0. Pairing with `goal.md` — constitution vs city plan

These two documents **complement** each other; they answer different questions:

| Document | Metaphor | Answers |
|---|---|---|
| [`goal.md`](goal.md) | **Constitution** | *Why does Tradelatest exist? What must never change?* |
| **This file** | **City plan** | *How do we evolve (research → strategy → production) without violating the constitution?* |

**Read order for a new contributor or LLM session:**

1. `goal.md` — governance priorities, happy flow, seven invariants, migration direction  
2. **This file** — WHO/WHAT/HOW, structural vs behavioral, Strategy Lifecycle, not-yet-built checklist  

Do **not** treat this file as overriding `goal.md`. A profitable but irreproducible path is still **unacceptable** under the constitution.

### 0.1 What `goal.md` owns (do not restate as “optional here”)

- **Governance order:** replay correctness → explainability → telemetry → advisory-AI, alongside
  a standing distinction (not a fifth rung): **structure validity ≠ execution validity** — "the
  pattern is valid" must never be read as "the trade is safe." See §1.  
- **Happy flow (production spine):** OHLCV → four engines → fusion → decision → planner → risk → trade  
- **Off hot path by design:** governance, training, AI assistant — observe/assist; do not silently steer live authority  
- **Seven invariants (laws of physics):** same inputs → same outputs; all four engines or reject; LLM advisory only; governance before promotion; additive telemetry; legal CRT transitions only; no hidden infra dependencies  
- **Migration direction:** monolith → observable → event-driven → microservices → LLM-friendly services (**context economy**)  
- **G001:** economic targets measured alongside (not above) invariants  

### 0.2 Four concepts that must stay separate

Often mixed; this architecture forbids collapsing them:

| Concept | Purpose | Lives in |
|---|---|---|
| **Market semantics** | Describe the market objectively | Ontology + formula registry + structural code |
| **Strategy** | Define *when* we are willing to act | Thresholds, gates, risk, sessions — config / Strategy package |
| **Models** | Estimate confidence / conformity / veto | WHO artifacts (CRT score path, Gauss, Zone, RR, optional BitNet, …) |
| **Governance** | Decide what may enter production | ValidationReport, promotion, `ACTIVE_VERSION`, audit log |

### 0.3 Layered stack (both docs combined)

```text
GOAL                    Why does the system exist?          ← goal.md
    ↓
INVARIANTS              What must never change?             ← goal.md
    ↓
MARKET SEMANTICS        What is the market?                 ← ontology + registry + structural code
    ↓
STRATEGY                When should we trade?               ← config / Strategy package
    ↓
MODELS                  How confident / conformant?         ← engines / optional BitNet
    ↓
RISK                    Can we afford it?                   ← Ultron / kill switch
    ↓
EXECUTION               Place or reject                     ← planner + broker path
    ↓
LEDGER                  Measure the outcome                 ← provenance + journal
    ↓
RESEARCH                Improve the next strategy           ← isolated harness → candidate only
```

---

## 0.4 Strategy Lifecycle (end-to-end — the actionable join)

This is the single path from **constitution** to **continuous improvement**.  
Every stage has an owner, an artifact, and a **must-not**.

```text
[1] Market semantics (stable)
        │  ontology + registry + candle/derived math + CRT topology
        │  MUST NOT: redefine formulas as “tuning”
        ▼
[2] Feature pipeline (deterministic)
        │  canonical feature vector
        │  MUST NOT: strategy-specific formula forks
        ▼
[3] Strategy package (versioned)
        │  features_used + thresholds + model pins + risk + provenance
        │  Today: largely production JSON; Target: Strategy Registry view
        │  MUST NOT: second formula authority
        ▼
[4] Research experiments (isolated)
        │  research_config* / harness; same features; vary strategy knobs only
        │  MUST NOT: write production; import promotion spine as authority
        ▼
[5] Qualification against G001 (+ honest costs/exits)
        │  trades/mo, RR, WR, DD, expectancy, PF, OOS as required by gate
        │  MUST NOT: promote on in-sample only or contaminated labels
        ▼
[6] Governance / promotion
        │  ConfigValidator → ValidationReport APPROVE → PromotionManager
        │  SHA-256, archive prior, promotion_log.jsonl
        │  MUST NOT: skip validator on normal path; silent ACTIVE_VERSION edit
        ▼
[7] Production activation
        │  ACTIVE_VERSION → production JSON → live/backtest entry points
        │  MUST NOT: env-only dual truth (F-058); programmatic CRT dual truth (F-057)
        ▼
[8] Decision ledger
        │  vector + config hash + model versions + thresholds + plan + outcome
        │  MUST NOT: unreconstructable “it worked once” trades
        ▼
[9] Continuous improvement
        │  findings / nulls / ΔG001 → next Strategy package (back to [3]/[4])
        │  MUST NOT: reverse killed findings without reopen conditions
```

### Lifecycle stage card

| Stage | Primary question | Success looks like | Blocked by (today) |
|---|---|---|---|
| 1 Semantics | Is the market concept defined once? | Ontology + registry + tests | Residual FM divergences (tracked) |
| 2 Features | Same OHLCV → same vector? | Deterministic pipeline | PIT/residual issues where open |
| 3 Strategy package | Can we name “what we trade with”? | Versioned thresholds+risk+models | No formal Strategy Registry yet |
| 4 Research | Isolated measurement? | Research configs only | Must keep spine isolation |
| 5 Qualify G001 | Economically interesting under honest rules? | EdgeReport / gates | Many axes already null (findings) |
| 6 Promote | Governed activation? | APPROVE + log + archive | — path exists |
| 7 Production | One active HOW? | ACTIVE_VERSION + consistent loaders | **F-057, F-058 open** |
| 8 Ledger | Fully reconstructible? | Provenance + outcome | Partial fields |
| 9 Improve | Belief update compounds? | Findings + next package | — |

**Lifecycle rule:** movement **forward** is research → qualification → promotion → production.  
Movement **backward** (changing semantics or formulas) is a **semantic/architecture change**, not a strategy experiment — higher bar, separate program.

---

## 0. Central rule (do not collapse)

> **Don’t confuse the target architecture with the current implementation.**

| Layer | Question | Primary artifacts (today) |
|---|---|---|
| **WHO** | Which models / contracts exist? | `active_models.yaml`, `models/*_registry.json`, MIAR |
| **WHAT** | What do market concepts mean? | `configs/formulas/market_ontology.yaml` |
| **HOW (formulas)** | How is each quantity computed? | `src/features/registry/*` → named callables (`candle_math`, `derived_math`, …) — **never `eval` YAML** |
| **HOW (runtime knobs)** | Which parameters run today? | `configs/production/ACTIVE_VERSION` → `configs/production/<version>.json` (active: `v2_multi_2026_04`) |
| **EXECUTION** | Score → decide → plan → risk → order | Feature pipeline · engines · fusion · planner · Ultron · backtest/live |

**WHO / WHAT / HOW in plain language:**

| Layer | Answers |
|---|---|
| WHO | Which models exist? |
| WHAT | What does `body_ratio` *mean*? |
| HOW (formula) | How is it *computed*? |
| HOW (runtime) | Which *threshold* is active today? |
| Execution | Should a trade happen? |

**Central recommendation for profitability work:**

> Keep **market semantics** stable and deterministic. Make **strategy behavior** (thresholds, model selection, risk parameters) configurable, versioned, and measurable.

---

## 1. North-star priorities (governance) vs G001 (economic)

**Governance order** (from `goal.md` / session doctrine — profit is not primary over integrity).
The four items rank; the fifth is a **distinction**, not a fifth rank — do not read it as
"Execution" placed after advisory-AI:

```text
replay correctness
  > explainability
  > telemetry continuity
  > advisory-AI

  (always holds, not ranked): structure validity ≠ execution validity
    — "the pattern is valid" must never be read as "the trade is safe to take"
```

**Economic objective G001** (machine-readable `goal` section in active production JSON; `enforce: false` today — measure gap, don’t hard-block):

| Metric | Target (active config shape) |
|---|---|
| Trades / month | min 20 · target 40 · max 80 |
| Avg RR | ≥ 2.0 |
| Win rate | ≥ 0.35 |
| Max drawdown | ≤ 10% |
| Risk / trade | 0.5% |
| Expectancy | ≥ 0.20R |
| Timeframes | M15 execution · H1 structure |
| Constraints | reaction-only · human execution |

**Authority Ladder (§6.5):** Information ≠ value ≠ authority ≠ architecture.  
Only **measured ΔG001** (plus governance promotion) grants production weight. Evidence alone does not.

**AI rule:** LLM is **advisory only** — never trade trigger, never autonomous planner, never risk override.

---

## 2. Structural market semantics (deterministic — stay code-backed)

These represent **the market itself**, not the trading strategy. Prefer **STRUCTURAL** freeze (Config-First):

| Keep deterministic | Examples / homes |
|---|---|
| OHLCV ingestion & schema | candle loaders, integrity |
| Candle geometry | `candle_math.py` — `body_size`, `candle_range`, `body_ratio = body_size/candle_range` (zero-range safe) |
| Feature formulas & FM identities | ontology (meaning) + registry (callables) + `derived_math` (e.g. `disp_strength`) |
| Canonical feature vector | `CANONICAL_FEATURES` / feature schema — pipeline emits deterministic vector |
| CRT state **topology** / legal transitions | `VALID_TRANSITIONS` / state_identity — structure of the story |
| Market structure geometry used by CRT | engine geometry in code; thresholds may be config |

**Do not** “optimize” formula identities as strategy knobs. Changing `body_ratio`’s definition is a **semantic** change, not a threshold search.

### Worked feature paths (current intent)

**body_ratio**

```text
OHLC → body_size, candle_range (candle_math)
     → body_ratio = body_size / candle_range
     → ontology FM (e.g. FM-010 class) + registry binding
     → FeaturePipeline column
     → canonical feature vector
     → engines / models that read the vector
```

**disp_strength**

```text
body_size, ATR, close → derived_math.disp_strength(...)
                       → registry maps ontology impl name → callable
                       → pipeline / vector
                       → CRT / consumers
```

(Residual: dimensional-mix / FM-030–031 family documented in findings — mechanism debt, not “free to redefine casually.”)

---

## 3. Strategy-related behavior (configurable — BEHAVIORAL)

Strategy stack (target and doctrine):

```text
Feature vector (fixed market semantics)
        │
        ▼
Thresholds / gates          ← config
        │
        ▼
Decision logic              ← config + code orchestration
        │
        ▼
Risk                        ← config (Ultron / kill switch / portfolio)
        │
        ▼
Execution plan              ← config (planner SL/TP/TTL profiles)
```

**Examples of strategy parameters (belong in config, not hardcoded forever):**

- `body_ratio > 0.68` (gate thresholds)
- `disp_strength > 0.55`
- ATR multipliers (breakout / SL buffer / expansion distance, etc.)
- Zone confidence / cluster thresholds
- Fusion weights / score thresholds
- Risk = 0.5% per trade, min RR, max DD, max trades/day
- Session allow-lists / instrument overrides
- `use_bitnet` + BitNet threshold (only when enabled)
- Model artifact paths / impl switches (`gaussian_impl`, zone registry path, …)

**Config-First maturity:** `HARD_CODED → CONFIG_WIRED → CONFIG_DRIVEN` (+ optional `GOAL_SEEKING`).  
New knobs: **fail-fast** `_require` / no silent defaults (“No silent Fall Back”).

**The STRUCTURAL/BEHAVIORAL split above is not a clean binary — one standing exception exists.**
CLAUDE.md §6.5's 2026-07-18 exception reclassifies feature-pipeline indicator **periods**
(`rsi_period`, `atr_period`, `ma_periods`, `bb_period`/`bb_std`, `macd_*`, `ema_fast_span`/
`ema_slow_span`) as BEHAVIORAL and config-driven, precisely *because* they are window/span
numbers, not geometric identities. **Geometric primitives stay STRUCTURAL** — `body_size` /
`wick_size` / `body_ratio` / `candle_body` / `upper_wick` / `lower_wick` are unaffected; there is
no "period" to tune in a fixed identity like `area = πr²`. Do not generalize the exception beyond
rolling-window/span periods — see CLAUDE.md §6.5 for the full boundary, not restated here.

---

## 4. WHO / WHAT / HOW file map (impact: does live trading change?)

| File / surface | Layer | Live trading impact (today) | Notes |
|---|---|---|---|
| `active_models.yaml` | WHO | Rarely direct | Identity/contracts/evidence mirror; loaders may diverge |
| `models/*_registry.json` | WHO / artifacts | Conditional | What is registered vs what path loads |
| MIAR | WHO intent | Docs/governance | Why each model exists; non-goals |
| `configs/formulas/market_ontology.yaml` | WHAT | **Sometimes** | Meaning backbone; trades change only if bound impl/pipeline path changes — **not** `eval` of full YAML |
| `src/features/registry/*` + `candle_math` / `derived_math` | HOW formulas | **Yes** if math path changes | Single compute authority |
| `ACTIVE_VERSION` + active prod JSON | HOW runtime | **Yes** | Primary strategy/knob pack today |
| `configs/formulas/market_shapes.yaml` | Shadow WHAT | **No** | → `market_shape` → research only |
| `configs/formulas/market_crt_states.yaml` | Shadow | **No** | → `crt_state_resolver` research/validation — **not** `crt_engine_v2` |
| `configs/market_reality/*`, `market_story_ontology.yaml` | Draft | **No / unwired** | Not load-bearing |
| `configs/research/research_config*.json` | Research HOW | **No** | Isolated harness |
| `configs/control_plane/monitors.json` | Ops | **No** | Dashboard monitors |
| `configs/promotion_log.jsonl` | Audit | Indirect | History of promotions |
| `market_router` **code** profiles | HOW leak | **Yes on some paths** | **F-057** — programmatic path can ignore prod JSON CRT knobs |

### Production spine (load-bearing HOW)

```text
ACTIVE_VERSION
    → production_config (get_active_version / get_prod_config / get_prod_section)
    → configs/production/<version>.json
    → FeaturePipeline knobs + engine/fusion/decision/risk/planner sections
    → EngineRunner / BacktestRunner / live_engine_hook
    → Live or backtest ledger
```

### Research spine (isolated)

```text
configs/research/research_config*.json
    → research.config.ResearchConfig
    → HypothesisRunner / scripts/research/*
    → Edge reports / findings
```

**Must never:** research imports forbidden spine writers or writes `configs/production/*` without promotion path (`docs/intent/400_research.md`).

### Shadow systems (validation, not authority)

```text
market_crt_states.yaml → CRTStateResolver → research parity / confusion matrices
market_shapes.yaml     → MarketShapeClassifier → shape_statistics / research
```

Real CRT authority for trades: **`crt_engine_v2` + production CRT knobs**, not the shadow resolver.

---

## 5. Target research loop (features fixed; thresholds / strategy vary)

```text
Historical OHLCV
        │
        ▼
Feature Pipeline          ← fixed market semantics
        │
        ▼
Semantic Feature Vector
        │
        ▼
Parameter / strategy search   ← thresholds, gates, risk, optional model pin
        │
        ▼
Evaluate (honest exits + costs)
  Win rate · PnL · PF · Drawdown · Expectancy · trades/month
        │
        ▼
Best *candidate* strategy config
        │
        ▼
ConfigValidator + human/governance review
        │
        ▼
PromotionManager → new version + ACTIVE_VERSION
```

**Rules:**

1. **Features (formulas) do not change** inside a threshold search.  
2. Research **proposes**; production **activates** only via promotion.  
3. Expect many **nulls** under realistic costs (F-019…F-027 family, etc.) — nulls are high knowledge-ROI.  
4. Keep **threshold optimization** and **model training** as **two separate** research activities.

---

## 6. BitNet’s role (target) vs today

> **Formalized 2026-07-29.** The one-paragraph sketch that used to live here
> (`Feature vector → BitNet → probability / confidence / veto score`) is **superseded** — it was
> wrong on both the input (BitNet reading the feature vector makes it a correlated fifth opinion,
> not an independent check) and the vocabulary (MIAR's locked term is **acceptability score** —
> never "probability", never "confidence"). Full specification:
> [`bitnet-design-specification.md`](bitnet-design-specification.md) ·
> gate ladder: [`bitnet_qualification_protocol.md`](../governance/bitnet_qualification_protocol.md).

**Target split (keep BitNet out of threshold search):**

```text
Feature vector
      └──► CRT · Gaussian · ZoneGate · RR        (the four specialists score independently)
                    │
                    ▼
           Specialist evidence bundle             (scale-invariant: ratios / z-scores only)
                    │
                    ├──► Fusion → Decision        (the approval path)
                    │
                    └──► BitNet → acceptability score → VETO channel (binding, negative-only)
```

BitNet reads the **panel's testimony**, not the candles the panel already read. Its authority
stage is unchanged (Safety · veto only); what changes is *what it looks at* and *what it can
perturb* — today it fires inside the CRT state machine and a reject **resets** it.

**Status: PROPOSED — `GATE-A` OPEN, not accepted.** `use_bitnet` stays `false`. This target
requires an explicit product decision per
[`bitnet-cpp-specification-v1-2026-07-21.md`](../implementation_plan/bitnet-cpp-specification-v1-2026-07-21.md)
§8.2, plus measured ΔG001 under the Authority Ladder (§6.5). Nothing here is built.

**Today (implementation truth):**

- Active config: `use_bitnet: false`, `gaussian_impl: heuristic`
- BitNet is **not** center of live decision path (F-004, F-055)
- When enabled by design: **safety veto / score**, not positive structure rediscovery (MIAR Stage 3)

**Do not** merge BitNet hyperparameter search into threshold grids without explicit experiment design and clean labels.

---

## 7. Target live trading path

```text
Live OHLCV
      → Features (deterministic)
      → Production / strategy config (versioned)
      → Deterministic gates + (optional) BitNet
      → Risk engine (Ultron — last line)
      → Execute (planner geometry; human/broker constraints as configured)
```

**Today live path (simplified):**

```text
OHLCV → features → CRT + Gaussian + ZoneGate + RR
      → fusion / decision → ExecutionPlanner → Ultron
      → live/backtest
```

(BitNet off; research spine separate; fusion gate state must be **config-declared** — see F-058.)

---

## 8. Strategy Registry (target packaging layer)

**Intent:** versioned **strategy** = feature *use* + thresholds + model pin + risk — comparable in research, activatable in production.

Illustrative shape (not a shipped schema):

```yaml
strategy:
  name: crt_breakout_v3
  version: "2026_07_v3"
features_used:          # subset of canonical / declared inputs — not new formulas
  - body_ratio
  - disp_strength
  - retest_depth
thresholds:
  body_ratio: 0.67
  disp_strength: 0.58
model:
  bitnet: null            # or pin artifact version when earned
  gaussian_impl: heuristic
risk:
  max_risk_per_trade_pct: 0.5
  min_rr_ratio: 1.5
provenance:
  parent_config: v2_multi_2026_04
  ontology_ref: market_ontology.yaml@...
  feature_schema_hash: <schema>
```

**Must complement, not replace:**

| Existing | Role |
|---|---|
| Production JSON + `ACTIVE_VERSION` | De-facto strategy pack today |
| `src/strategies/s01…s10` | Strategy modules |
| MIAR / `active_models.yaml` | Model intent / identity |
| `models/*_registry.json` | Artifact versions |
| Promotion path | Only activation mechanism |

Strategy Registry = **thin packaging / naming** over these authorities — **not** a fifth conflicting source of formula meaning.

---

## 9. Decision / trade ledger (target completeness)

Every trade (research candidate and live) should be reconstructible:

| Field | Purpose |
|---|---|
| Timestamp / instrument / TF | When & where |
| Feature vector (or hash + store) | Market state at decision |
| Production / strategy config version + hash | HOW knobs |
| Model versions (CRT path, Gauss, Zone, RR, BitNet if any) | WHO artifacts |
| Thresholds / gates that fired | Why allowed |
| Prediction / scores | Engine outputs |
| Decision + risk outcome | Approve/reject + reason |
| Execution plan (entry/SL/TP/TTL/size) | Geometry |
| Outcome after close | Realized R, exit reason |

**Shipped 2026-07-29 (backtest):** `TradeProvenanceV1` stamped at trade-open with
`config_version` / `config_hash` / `promotion_version` / `model_version` / `strategy_id`, plus
`feature_vector_sha` (sha256 of the canonical vector) and `gates_fired` (the full `CRTConfig`
threshold snapshot) on every ENTRY line.
**Remaining gap:** the live path (`live_engine_hook.py`) shares the same config/model/strategy
stamping (`_build_provenance_base`) but does not yet stamp `feature_vector_sha` or `gates_fired`,
and `trade_id` canonicalization across backtest/live is a separate, already-tracked initiative
(`journal.trade_identity_v1_0`) — out of scope for this config-authority change. See §14.F.

---

## 10. Current vs target (explicit)

| Concern | **Today** | **Target** |
|---|---|---|
| Market formulas | Ontology + registry + code (good) | Unchanged principle |
| Strategy knobs | Widened census (`src/runtime` + 3 more packages) + `_require` fail-fast boundary applied | Remaining BEHAVIORAL hardcodes tracked, not zero |
| Single HOW source | **F-057 remediated** (2026-07-29) — `market_router` is config-driven (`configs/production/*.json` `market_router` section); `classify_market()` raises `UnknownInstrumentError` on a miss instead of defaulting to FOREX; programmatic path loads via `load_prod_config_from_registry` | Achieved — parity proof: `scripts/analysis/ledger_parity.py` |
| Engine gate in backtest | **F-058 remediated** — `backtest.engine_gate_enabled` + `backtest.bypass_zone_invalid` are both config-declared, strict-read; env is an explicit override that WARNs on disagreement | Achieved (epoch declared ON) |
| BitNet | Off / research; evidence-consumer redesign **PROPOSED** (§6, `GATE-A` OPEN) | Optional earned veto/score slot — ladder: [`bitnet_qualification_protocol.md`](../governance/bitnet_qualification_protocol.md) |
| Strategy packaging | **Shipped** — `StrategyPackage`/`StrategyRegistry` (§8, §14.C) project prod JSON + model registries into a versioned, hashable view | Named Strategy Registry versions — achieved as a projection; feature-subset declaration and code-free harness loading remain open (§14.C) |
| Research | Isolated configs + M4-style gates; `job_kind` separates threshold-search from model-retrain jobs; `goal_alignment.py` reports G001 gap per candidate | Same + explicit strategy compare (strategy-aware research loading still open, §14.C) |
| Ledger | **Substantially shipped** — `TradeProvenanceV1` wired at trade-open (backtest + live), `feature_vector_sha` + `gates_fired` on backtest; live shares config/model/strategy stamping via the same `_build_provenance_base` but not yet the vector hash / gate snapshot | Full vector + versions + outcome — backtest complete, live partial (§14.F) |
| Semantic OS (YAML runs all states) | Not goal | **Deferred** — fights STRUCTURAL freeze |
| Auto-promote best grid | Forbidden | Still forbidden |

---

## 11. User intent freeze (session + domain contracts — no loss)

### Standing user / session directives

- **No silent Fall Back** — fail closed; no plausible invented defaults  
- **Config-first:** Frozen Engine + Mutable Behavior; Evidence > Doctrine > Preference  
- **Owner:** no soft defaults on new knobs; fail-fast  
- **Ontology supremacy for MEANING** (with mechanical constraints: frozen runtime keys flat/additive; production behavior still needs parity + promotion)  
- **Remaining work after substrate:** research for **ΔG001**, not endless ontology construction  
- **OBSERVATION_ONLY** for audits until behavior change authorized  
- **AI:** deterministic plans / advisory only; writes confirmed  
- **Memory:** experiments must not be forgotten; findings > chat-only  
- **Null findings high ROI** — stop dead ends  

### Domain user thoughts (`docs/intent/`)

| Domain | User thought |
|---|---|
| Governance | “Don’t repeat mistakes.” |
| Execution | “Four independent opinions → fuse → plan → risk — not a black-box buy/sell.” |
| Risk | “Survive a string of losses; one bad trade must not end the account.” |
| Memory | “Experiments should not be forgotten.” |
| Research | “Experiment freely with zero risk to the live path.” |
| Agent | “Helpful AI, predictable, every write confirmed, plans pre-defined.” |
| Preservation | “Most bugs are documentation entropy.” |

### Model stage intents (MIAR — locked questions)

| Stage | Question | May decide trade? |
|---|---|---|
| Market understanding (CRT, Gauss, Zone, RR, …) | What is the market? | **Never alone** |
| Opportunity (TradeNet, trained RR, …) | What to expect if I trade? | Predict only |
| Safety (BitNet) | Unsafe? | **Veto only** |
| Decision (fusion + DecisionEngine) | Approve? | Yes (approval) |
| Execution (planner) | How execute approved? | After approval |
| Measurement | Did intent hit G001? | No |

Vocabulary: Probability ≠ Score ≠ Confidence; bare “quality” forbidden without qualifier.

---

## 12. Anti-goals (explicitly not the target)

1. Fully **semantic-executable OS** where Python “doesn’t know DISPLACEMENT” and all transitions live only in freeform YAML.
   > **Scope note (2026-07-29):** this anti-goal targets **runtime** execution — Python
   > deferring live decision behavior to freeform YAML instead of code. It does **not** reject
   > **design-time** generation of documentation/registries from a validated, schema-enforced
   > semantic registry (`configs/formulas/market_ontology.yaml` `reasoning_capabilities` +
   > [`REASONING_CAPABILITY_REGISTRY.md`](../governance/REASONING_CAPABILITY_REGISTRY.md)) —
   > that registry is never read on the runtime binding path (`validate_registry()` stays
   > clean; CLAUDE.md §6.6's two mechanical constraints). Recorded here explicitly so that
   > work is never mistaken for reopening this anti-goal.
2. **BitNet-centric** live brain replacing CRT structure.  
3. **Auto-promotion** from research grids to `ACTIVE_VERSION`.  
4. Treating **RAG / more models / more docs** as substitutes for measurement integrity.  
5. Searching **feature formula definitions** as if they were strategy thresholds.  
6. Silent dual truths (env vars, hardcoded router profiles, soft defaults).  
7. Research writing production or importing promotion/spine writers.

---

## 13. Implementation sequence (ROI-ordered)

Aligned to **Strategy Lifecycle** (§0.4). **All 9 items implemented 2026-07-29** — see §14 for
per-item evidence and open sub-items.

1. ✅ **Lifecycle [7] integrity:** F-057 — production JSON authoritative on programmatic path; fail unknown instrument. `src/config_layer/market_router.py`.
2. ✅ **Lifecycle [7] integrity:** F-058 — engine gate + bypass flags declared in config; epoch-scoped. `src/runtime/backtest_v2.py`.
3. ✅ **Lifecycle [3]/[7] config completeness:** census widened + `_require` boundary applied. §14.B (one sub-item — the section-mapping doc — remains open).
4. ✅ **Lifecycle [8] honest baseline:** `scripts/analysis/ledger_parity.py` (CLI = programmatic).
5. ✅ **Lifecycle [3] packaging:** `StrategyPackage`/`StrategyRegistry`, §8. §14.C (two sub-items — curated `features_used`, code-free harness loading — remain open).
6. ✅ **Lifecycle [4]–[5] research loop:** `job_kind` separation + `goal_alignment.py` vs G001. `src/research/`.
7. ✅ **Lifecycle models slot:** `scripts/research/model_shadow_protocol.py` (generalized from the BitNet-specific driver) + `bitnet_qualification_protocol.md` (`BN_QUAL_V1`). Enable flag still gated — never folded into threshold search.
8. ✅ **Lifecycle [8] completeness:** `TradeProvenanceV1` wired at trade-open (backtest + live). §14.F (backtest/live parity on `feature_vector_sha`/`gates_fired` remains open).
9. ✅ **Lifecycle [9] / DX:** `scripts/analysis/config_reachability.py --graph` → `docs/architecture/config-consumer-graph.generated.{json,md}`.

---

## 14. Not yet built / incomplete checklist

Use as a living checklist. Mark items when closed with evidence (test + SESSION LOG + finding update).

> **Reconciled 2026-07-29.** Every `[x]` below was verified against the actual artifact before
> being ticked (not assumed from a summary) — a box with a claim it couldn't support was left
> unchecked with a note instead. See §13 for the corresponding sequence items.

### A. Measurement integrity (blocking for honest strategy work)

- [x] **F-057** remediated — `market_router` is config-driven (`configs/production/*.json`
      `market_router` section: `classes` + `symbol_map`); `ConfigBuilder`/`load_prod_config_from_registry`
      is authoritative on the programmatic path (`src/config_layer/market_router.py`)
- [x] Unknown instrument **fail-closed** — `classify_market()` raises `UnknownInstrumentError`
      instead of defaulting to FOREX (`src/config_layer/market_router.py`)
- [x] **F-058** remediated — `backtest.engine_gate_enabled` **and** `backtest.bypass_zone_invalid`
      are both config-declared, strict-read; env is an explicit override that WARNs on
      disagreement (`src/runtime/backtest_v2.py`)
- [x] F-037 / active_models docs reconciled with declared gate epoch
- [x] Parity proof: `scripts/analysis/ledger_parity.py` — programmatic vs CLI ledger agreement
      on fixed config + corpus  

### B. Config-first / strategy knobs

- [x] Census of remaining BEHAVIORAL hardcodes on spine — corpus widened from
      `{core, engines, config_layer}` to include `src/runtime` (where F-056 found real
      undeclared trade-affecting constants) + 3 more packages (`scripts/analysis/behavior_census.py`)
- [x] Each new knob: `_require` / `from_prod_config`, no silent default — applied to every knob
      introduced this pass (`market_router`, `bypass_zone_invalid`, `job_kind`, strategy fields)
- [ ] Document which prod JSON sections map to Feature / Threshold / Decision / Risk / Execution —
      **not done.** No such mapping document exists yet; verified absent, not merely unwritten
      by omission.

### C. Strategy Registry (packaging)

- [x] Schema for strategy version (name, features_used, thresholds, model pins, risk, provenance) —
      `StrategyPackage` (`src/strategies/strategy_package.py`) matches the §8 shape exactly.
      **Caveat:** `features_used` currently defaults to the full `CANONICAL_FEATURES` schema
      because no consumer in this codebase declares a used-subset yet — the field exists, curated
      subsets do not (module docstring is explicit about this).
- [x] Mapping: strategy version ↔ production config version / hash — `.content_hash()` +
      `provenance["config_hash"]` on every package
- [ ] Research harness can load strategy package without editing code — **not done.** Verified:
      `src/research/{config,runner,cli}.py` contain zero references to `StrategyRegistry` or
      `strategy_id`. `StrategyRegistry.load()`/`.resolve_for_instrument()` exist and work, but
      only from a Python call site today — that is "editing code," not "loading via config."
- [x] Promotion activates strategy version only via existing governance — true by construction:
      `StrategyPackage` is a read-only projection (`from_active_config()`), so there is no
      separate strategy-promotion path to diverge from the existing one
- [x] Does **not** redefine ontology FMs — module docstring states the projection invariant
      explicitly; grepped for formula/FM references, found none  

### D. Research loop

- [x] Standard experiment record: config hash, feature schema hash, metrics, OOS, costs model —
      `src/research/provenance.py` `provenance_block()` extended 2026-07-29 with
      `production_config_block()` (`config_version` / `config_hash` / `feature_schema_hash`,
      fail-open). **`strategy_id` is deliberately NOT included** — no research config currently
      declares one (`ResearchConfig` has no such field); wiring it through is the same gap as the
      unchecked box above, not a smaller omission.
- [x] Separation enforced: threshold search vs model retrain jobs — `job_kind` field on
      `ResearchConfig`, restricted to `{threshold_search, model_retrain, unspecified}`
      (`src/research/config.py`)
- [x] No write to production from research — verified: zero references to `configs/production`
      anywhere in `src/research/*.py`
- [x] Expectancy/PF/DD/trades-per-month vs G001 reported every candidate —
      `src/research/goal_alignment.py` (`goal_report_for_edge`, `attach_goal_reports`)  

### E. BitNet / models (earned only)

- [x] BitNet remains off on active until ΔG001 authority — `use_bitnet: false` unchanged
- [x] Shadow protocol + clean labels before enable — `scripts/research/model_shadow_protocol.py`
      generalizes the BitNet-specific shadow driver; clean-label requirement now formalized as
      `BN_QUAL_V1` GATE-L (see [`bitnet_qualification_protocol.md`](../governance/bitnet_qualification_protocol.md))
- [x] MIAR non-goals respected (veto, not structure rediscovery) — enforced mechanically by
      `tests/test_miar_registry.py` (14/14 green, including the new sidecar zero-authority tests)
- [x] Loader/registry/runtime alignment per family (lineage audits) — five lineage audits exist
      (Gaussian/ZoneGate/RR/BitNet/TradeNet), all cross-referenced from MIAR §7  

### F. Decision ledger completeness

- [x] Feature vector on every trade open — `feature_vector_sha` (sha256 of the canonical vector)
      on **backtest**; **absent on live** (see consistency note below)
- [x] Config version + hash always present — `config_version`/`config_hash` via
      `_build_provenance_base`, shared by **both** backtest and live
- [x] All engine/model versions that influenced decision — `model_version`/`strategy_id`, shared
      by both backtest and live via the same function
- [x] Thresholds/gates that fired — `gates_fired` (full `CRTConfig` snapshot) on **backtest**;
      **absent on live** (see consistency note below)
- [x] Plan + risk decision + outcome joinable — via `trade_id` on backtest
- [ ] Provenance fields consistent across backtest and live — **partial, not done.**
      `config_version` / `config_hash` / `model_version` / `strategy_id` **are** consistent (both
      paths call `_build_provenance_base`). `feature_vector_sha` and `gates_fired` exist only on
      backtest. `trade_id` canonicalization across the two paths is a separate, already-tracked
      initiative (`journal.trade_identity_v1_0`) and was explicitly out of scope for this pass —
      live still synthesizes `f"{symbol}_{candle_idx}"`.  

### G. Shadow / draft configs (explicit non-spine)

- [ ] `market_shapes.yaml` documented as research-only (done in this framing)  
- [ ] `market_crt_states.yaml` / resolver parity maintained **without** becoming live authority  
- [ ] Decide fate of unwired `market_reality` / `market_story_ontology` (wire under research contract or archive)  

### H. Documentation / LLM navigability

- [x] This doc linked from knowledge map / goal companions (2026-07-28)  
- [x] Constitution (`goal.md`) ↔ city plan (this file) pairing stated (§0)  
- [x] Strategy Lifecycle frozen end-to-end (§0.4)  
- [x] Generated config→consumer graph — `scripts/analysis/config_reachability.py --graph`  
- [ ] USER intent pack remains loadable without full session-log token burn  

### I. Strategy Lifecycle operationalization

- [ ] Named stage artifacts for [3] Strategy package (see Strategy Registry §8)  
- [ ] Research entry docs cite lifecycle stage (4–5) and refuse formula edits as “tuning”  
- [ ] Promotion checklist explicitly maps to lifecycle [6]→[7]  
- [ ] Ledger schema maps to lifecycle [8] completeness  
- [ ] Continuous improvement [9] always lands a finding or SUPERSEDED update when a strategy is killed  

---

## 15. Related findings (do not reverse without evidence)

| Id | Relevance |
|---|---|
| F-001 | Intelligence not binding constraint — governance/throughput/consumption |
| F-004 / F-055 | BitNet gate inert/off or non-improving when tested |
| F-019…F-027+ | Entry/selection/exit falsifications under honest costs — threshold search may return null |
| F-037 / F-058 | Backtest fusion gate truth / env split-brain — **F-058 remediated 2026-07-29** (§14.A); F-037's gate-OFF corpus stays valid for its own epoch, not retro-invalidated |
| F-048 | DecisionEngine no longer owns economic RR; Ultron does |
| F-057 | CRTConfig programmatic split-brain — **remediated 2026-07-29** (§14.A, `market_router.py`); finding preserved as history per CLAUDE.md §6.2 rule 4, not reversed |
| F-041B / F-036 | Zone labels / non-pivotal fusion — don’t treat zone as free edge |

---

## 16. One-page summary diagram

```text
                 DOMAIN TRUTH (stable)
         ontology + registry + candle/derived math
         CRT topology (code) + canonical features
                           │
                           ▼
              SEMANTIC FEATURE VECTOR
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   STRATEGY CONFIG    OPTIONAL MODEL     RISK CONFIG
   thresholds/rules   BitNet / etc.      Ultron knobs
   (versioned)        (earned only)      (versioned)
          │                │                │
          └────────────────┴────────────────┘
                           ▼
                    DECISION → EXECUTE
                           │
                           ▼
              PROVENANCE LEDGER + OUTCOMES
                           │
         Research compares many strategy versions
         Promotion activates one version only
```

**Frozen sentence:**

> Market semantics define what the market *is*. Strategy configuration defines when we are *willing to act*. Models may advise or veto. Risk may stop us. Only measured improvement under governance changes production.

---

## 17. Change control for this document

- **Update** when target framing changes, a checklist item closes, or a finding reverses a premise.  
- **Do not** treat this doc as runtime authority (Tier-3/4 relative to `ACTIVE_VERSION` + code schema).  
- Closing a checklist item requires: code/config evidence, tests where applicable, SESSION LOG, and findings update if a registered conclusion moves.
