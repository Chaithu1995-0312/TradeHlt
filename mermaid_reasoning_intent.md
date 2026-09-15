# Intent trace — ChatGPT research plan × six-phase schema

Recorded 2026-09-15. Schema = `mermaid_boxes_phased.csv` + `mermaid_phases_linked.csv` + phase inner CSVs. Not a finding. Not promotion. Not P-GOAL-04.

## Your intent (traced)

You are not asking to wire ChatGPT’s “green candle + 1:3 RR” rule into the engine.

You are asking to use **general trading language as a reasoning curriculum**, then **translate** it onto the six-phase architecture you just built, with **MarketContext in the center**, not Trade.

Locked chain (your words, mapped):

```
MarketContext → EvidenceBundle → DecisionRecord → TradeObject → Outcome → Research
```

Not:

```
Predict → Trade
```

Not:

```
HTF → CRT → Buy
```

Lane: **semantic certification first**, then measurement, then economic qualification. CRT stays **structure**, not a strategy. P-GOAL-04 stays closed. `features.market_context` is already **shadow-only** (`src/features/market_context.py` — nothing on the decision spine consumes it).

## Two layers in the ChatGPT paste (do not collapse)

| Layer | What it is | What to do with it |
|---|---|---|
| A. Beginner OHLC tutorial | Should I trade / when / where; HH-HL; pullback; SL/TP; session; close>prior high | **Hypothesis vocabulary.** Map → measure. Do not add to `crt_engine_v2`. |
| B. Reasoning-layer brief | Observation/Evidence/Decision/Execution/Measurement planes; MarketContext-first; folklore must not contaminate the framework | **This is your intent.** Aligns with six-phase join + existing research isolation. |

If a later session treats Layer A as the spec, that is a miss.

## Schema is ready (where each plane already lives)

```
P5 operator     agent.cli / :8787     observes; pipeline_mode is the only src caller of promotion
P4 governance   promotion / Semantic OS / identity     hang-off; P1 does not import it
P1 candle spine ohlcv → features → CRT → engines → fusion → decision → planner → Ultron
P2 live rails   live_rail + hook bridges               paper TickDB; MT5_CANDLES = None
P3 sidecars     strategies / BitNet / CognitiveBus     imported ≠ live authority
P6 research     cli → HypothesisRunner → M4 qualify    imports P1; P1 does not import P6
```

Direction already measured: **P1 → P4 = 0, P1 → P6 = 0.** Research and promotion hang off and reach down.

## ChatGPT questions → planes (not into the engine)

| ChatGPT question | Plane | Six-phase home | Already in repo |
|---|---|---|---|
| Should I trade? | Decision | P1 `DecisionEngine` (semantic) then `UltronRiskGate` (capital) | Yes. Semantic ≠ capital (F-048). |
| When enter? | Decision / Execution | P1 planner + CRT RETEST/EXECUTION | Yes as **structure**. Not proven as edge (F-086). |
| Where exit? | Execution / Measurement | P1 planner SL/TP; P6 `forward_walk` | Exit is not the binding constraint (F-087). |
| Trending vs ranging vs vol | Observation | P1 features + `regime.regime_classifier` (P2 hook) + `MarketContext` (shadow) | Yes. Contemporaneous vol-regime not consumable (F-030). |
| HH/HL / LL/LH | Observation | Swings / `trend_strength` / structure predicates | Yes. Centered swings PIT-unclean (F-051). |
| Unclear → no trade | Decision | Reject / no EXECUTION | Yes as behavior. “No trade” is the default under nulls. |
| Pullback at support | Observation | CRT RETEST + range boundary | Named, not profitable as Visual CRT (F-081/F-084). |
| SL under swing / RR 1:3 | Execution | `execution_planner` + Ultron `min_rr_ratio` | Cost/width dominate (F-025, F-082, F-087). RR does not create entry information. |
| London / NY session | Observation | FM-052 session; `session_windows` filter | Session mislabel vs broker (F-066). Session not a BNB lever (F-017). |
| Close > prior high + body > avg | Observation | Displacement + `body_ratio` (FM-010) | Directional displacement is law (F-074). Morphology ≠ expectancy (F-023). |
| Green candle ≠ buy | Observation | Candle polarity vs trend | Matches repo: one bar ≠ trend. |
| Cannot buy open knowing close | Measurement | No lookahead; bar OPEN is MT5 time (F-098) | Already a constraint. |
| 20-bar lookback | Observation | Config periods (ema/ATR windows) | Behavioral knobs. Not a new object. |

## Translation table (ChatGPT’s later table, grounded)

| Trading word | Do not invent | Existing object | Phase |
|---|---|---|---|
| Uptrend | New “trend engine” | `trend_strength`, HH/HL swings, `MarketContext` Trend category, `regime_classifier` | P1 / P2 |
| Range / box | New range detector | CRT `RANGE`, mother range (research) | P1 / P6 |
| Breakout | Wire as buy | CRT `DISPLACEMENT` / `EXPANSION` (structure) | P1 |
| Liquidity sweep | “Stop hunt” folklore | CRT `SWEEP` | P1 |
| Pullback | Auto RETEST trade | CRT `RETEST` pathway | P1 |
| Reversal | CHoCH as signal | SMC CHoCH feature; opposite displacement | P1 |
| Momentum | New oscillator | `momentum_score` (F-061 scale defect on live path) | P1 |
| Support / resistance | New S/R engine | Range high/low, HTF `parent_crt`, PDH/PDL | P1 |
| Bullish candle | Buy | `close > open` on one bar | P1 |
| Bullish trend | Many HH/HL | Sequence, not one candle | P1 |
| Should I trade | Signal | DecisionRecord + Ultron | P1 |
| Outcome | PnL as proof of meaning | P6 `forward_walk` + M4 qualify | P6 |

`MarketContext` already answers “what is happening on this bar?” from ontology categories. It is **not** on the spine. Centering reasoning on it does **not** require activating it. Activation would be a separate gated behavior change.

## What ChatGPT got right (keep)

1. OHLC cannot certify the future; it can only mark **favorable-looking situations**.
2. Candle color ≠ trend. Context > color.
3. You do not know the close at the open — no lookahead.
4. Generic LLMs know folklore; they do not know **this** CRT / resolver / findings.
5. Translate concepts → measurable objects → accept/reject. Do not assume → add to engine.
6. Reasoning chain should be Observation → Evidence → Decision → Execution → Measurement.
7. Center on **context**, because a trade is an outcome.

## What ChatGPT must not become (kill on contact)

1. A 4-step buy setup as production logic.
2. “Body > average and close > prior high” as a new CRT transition.
3. Session-open as a proven lever (already measured on crypto).
4. RR 1:3 as expectancy (exit/cost is not the information bottleneck).
5. Teaching the **framework** trading. The framework already **measures** trading claims.
6. Opening P-GOAL-04 or a live book because the tutorial asked “should I trade?”

## Findings that already speak to Layer A (do not re-mine)

- F-019…F-027, F-035, F-081, F-084, F-086, F-097: entry information / context families do not clear economic gates on the objects measured.
- F-023: morphology separates SHAPE, not expectancy.
- F-002 / F-021: selection ≫ SL/TP; spine RETEST selection collapsed to session on crypto.
- Sense A: CRT = structure, not a complete strategy.

These do **not** say “never look at HH/HL.” They say a ChatGPT setup is **not authority**.

## How this sits on the six-phase join

```
P1 MarketContext + CRT + engines     Observation + Evidence  (shadow MarketContext; live evidence = engine scores)
P1 DecisionEngine + Ultron           Decision
P1 planner + P2 rails                Execution
P6 runner / forward_walk / M4        Measurement  (updates research, does not write ACTIVE_VERSION)
P5                                   Operator view of the chain
P4                                   Promotion only after G001 — currently unearned
```

The missing work, if you continue this intent, is **not** a new engine. It is a **Trading-concept → existing node** catalog (ChatGPT’s 100–200 map), each row: concept · existing object · phase · CURRENT vs folklore · already-measured finding · gap or refuse.

That catalog is semantic certification. It is not a strategy.

## Goal refinement (user 2026-09-15)

Stated goal: find strategies that earn money **through backtest**, by **monitoring feature configuration + state ranges + HTF ranges aligned**, and keeping the alignments that **backtested successfully**.

That is **intent**, not Predict→Trade:

```
aligned (feature config × feature/CRT state × HTF range)
    → measure on a production-shaped walk
    → keep cells that earn
    → monitor those same cells
```

Predict→Trade would skip the alignment and ask “is this bar a buy?”

Hard constraint from this repo: `backtest_v2` does not run ExecutionPlanner or UltronRiskGate (P-FLOW-13). A green book on that kernel is **not** the live trade object (F-088, F-010). Mining must name the walk (geometry + cost + fill) or the monitor will watch a ghost.

## O-APRIL-RETEST-001 (2026-09-15)

Observation, not a finding. In April 2026 on the H1 run, both RETESTs were outside CRT session windows → 0 EXECUTION. 0 trades ≠ 0 structure.

Clock freeze (language only, not an ontology edit): **Parent CRT** = calendar H4. **HTF RESET** = count-window rollover (16 M15). Do not merge. Promoting this split into the ontology is a separate governed change.

Largest April contraction is SWEEP → DISPLACEMENT (67 → 10), not the session gate. Session vs EXECUTION is a full-corpus RETEST hypothesis (`P(EXECUTION|RETEST, in_session)` vs off_session), not an April conclusion.

## RP-STATE-TO-RR-001 (2026-09-15)

Bridge from CRT occupancy to RR is a **TradeCandidate** (not in code). Do not join 94k `clean_labels` to H1 `events.jsonl` (`IllegalJoinError`, different grain). Phase B = state-entry bars on a named run + named geometry + named walk. Start at SWEEP/DISP/EXP, not EXECUTION n=4. Not a finding.

