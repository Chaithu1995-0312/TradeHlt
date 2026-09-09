# Unifying the Economics Layer — CRT Resolver Lineage, Pass 2

**Stance:** lead trading-systems architect. Defaults are assumed and stated, not asked.
Domain checks are injected from how real FX/metals desks fail, not derived from this
repo's existing tests.

---

## Where we are

**Shipped this session** (tests green, uncommitted):

| Artifact | What it closed |
|---|---|
| `src/data_ingestion/corpus_gate.py` | One admission seam: IDENTITY -> SEQUENCE -> PLAUSIBILITY (D-1..D-4). `backtest_v2._preflight_dataset` delegates to it. |
| `src/features/resolver_supply.py` | The 17,563-bar supply divergence, closed **by construction**. Rewired caller reproduces the other series exactly: RANGE 21,745 / SWEEP 15,186 / EXPANSION 7,092. |
| `crt_state_identity.yaml` | `determined: true`, `supply_set: canonical_v5_plus_nonvector`, `constructor_id: 61ef9dfe...` |
| 20 new floors | `test_corpus_gate.py` (9), `test_resolver_supply.py` (11); identity floors 67 -> 69 |

**What the economics trace then found, and this document is about:** the repo has
**two independent economics systems that never reconcile.** That is now the binding
architectural defect. Everything below serves closing it.

---

## Drift register — both consolidation passes

| Claimed | Established truth |
|---|---|
| "the resolver we developed yesterday" | Resolver is 2026-07-24. Yesterday was the identity / `constructor_id` layer around it. |
| "dataset integrity layer" (one thing) | Two: `validate_dataset` (runtime sequence) vs BC-1..BC-6 corpus admissibility. |
| Warmup 78 = 12 days of context | 78 is **emergent** -- `finalize()` has no warmup knob, it `dropna`s. A days-based value can only be an additional floor. |
| `rsi_state` explains the divergence | **Falsified.** It is `when:`-named only by `EXECUTION`, which `GAP-RESOLVER-001` declares unreachable. |
| Pass-1 plan: enriched-vs-canonical *values* differ | **False by construction.** `build_feature_vector` reads the same finalized frame. The real surface was extra **keys** + NaN coercion. |
| "the 01:00 gap bars are your call" | **Superseded — I make the call below.** It is a measurement-validity question, not a preference. |
| `partial_tp_breakeven_enabled` does breakeven | It is a **half-way trail** (`crt_engine_v2.py:2515`). Name retained deliberately, guarded (F-088). |
| One economics model | **Two.** Unresolved until this document is executed. |

---

## The defect: two economics systems

**System 1 — research.** Gross geometry, cost subtracted after.

```
risk_distance = sl_atr_mult * atr                     # pure ATR, frozen
TP_HIT  -> rr = reward_distance / risk_distance       # a constant
SL_HIT  -> rr = -1.0 exactly (unless SEM-016 adverse_fill)
net_rr  = gross_rr - cost_r ;  cost_r = cost_price / risk_distance
```

**System 2 — production ledger.** Cost baked into fills, R derived from the fill.

```
entry_fill = entry_raw + slip + spread_half
risk_pips  = |entry_fill - sl_price| / pip_size       # <-- denominator MOVES
pnl_rr_net = (price_move_net / pip_size) / risk_pips
```

They cannot agree even on identical inputs, because they do not share a unit.

### The subtle one, and it is a real statistical defect

System 2 computes R off the **fill**. A 0.1xATR entry slip against a 1.5xATR stop moves
the denominator ~6.7%, so every R in that trade is scaled by ~1/1.067 -- and the scale
factor differs per trade with the slippage draw. Averaging those numbers averages
quantities measured in **different units**. Expectancy, PF and t-stats computed over them
are not on a ratio scale.

Every desk I know of freezes R at order time off the *intended* levels. This is a bug
fix, not a preference.

---

## Decisions I am making on your behalf

All five ship **default-OFF behind config** and are then measured -- this repo's own
proven idiom (F-061 `normalization_basis`, F-066 `session_timestamp_basis`, F-082
`ComponentCostModel`). Default-off means the current ledger stays byte-identical and the
correction is reachable, not that the correction is optional.

**DEC-1 · R is frozen at order time.**
`risk_basis = |entry_intent - stop_intent|`, computed once when the order is planned,
recorded on the trade, and used as the denominator by *both* systems forever after.
Slippage then correctly shows up in the numerator (worse PnL) instead of silently
rescaling the unit.

**DEC-2 · Session-gap entries are embargoed.**
D-4 found 25 bars with price gaps over 3x median TR; **24 of 25 are the 01:00 bar**, prior
bar always 23:45. You could not have transacted at any price inside that gap. Treating the
gap bar as a founding SWEEP/DISPLACEMENT measures a path that did not exist, and a
17.8x-TR bar clears `expansion_atr_min_distance` and any `body_ratio >= 0.70` gate
trivially. Rule: **no founding event and no new entry on the first bar after a session
gap**; an already-open position still evaluates its stop against it (the gap is real risk,
it just is not an opportunity). Config: `feature_pipeline.session_gap_entry_embargo_bars: 0`.

**DEC-3 · Limit fills require trade-through; stops fill on touch, and slip.**
Both kernels currently fill TP on `high >= tp` (`multi_tp_walk.py:300-301`, and the same
in `forward_walk`). A resting limit needs the market to *trade through* it, not graze it
with a wick; a stop becomes a market order on touch and slips. That asymmetry is the
single most common source of optimistic backtest bias in the industry. Rule:
`high > tp` for a long limit, touch-and-slip for stops (SEM-016 already does the stop
half). Config: `research.fill_model.limit_requires_trade_through: false`.

**DEC-4 · Measured cost is the default where a calibration exists.**
`ComponentCostModel` for XAUUSD/metals (F-082 measured half-spread $0.045 / commission
$0.040 / stop slip $0.090); flat 12 bps only where nothing is measured; an instrument
declared-but-unmeasured **raises** rather than silently defaulting. Flat 12 bps is 11x too
punitive on gold -- that is not conservatism, it is a wrong number in both directions
depending on the trade.

**DEC-5 · `multi_tp_walk` is the single research kernel.**
`forward_walk` is retained as its degenerate case -- already proven by
`test_degenerate_config_reduces_to_forward_walk`. One kernel, one geometry, one place to
fix a fill rule.

---

## Target architecture

Three objects, replacing two parallel stacks. This is the standard shape: backtest and
live differ only in **where bars come from** and **who reports the fill**, never in how
PnL is computed.

```
                 ┌──────────────────────────────────────────┐
   order intent  │  FillModel        src/execution/fills.py │  bar -> fill price
   (entry, sl,   │   · stops: touch + slip (+ gap -> open)   │
    tp1, tp2)    │   · limits: trade-through, may not fill   │
                 │   · owns SEM-015 cost + SEM-016 adverse   │
                 └────────────────────┬─────────────────────┘
                                      v
                 ┌──────────────────────────────────────────┐
                 │  Accountant       src/execution/ledger.py│  fills -> PnL, R
                 │   · risk_basis frozen at order time (DEC-1)│
                 │   · partial at TP1, half-way trail        │
                 │   · rr = pnl_price / risk_basis           │
                 └────────────────────┬─────────────────────┘
                                      v
        ┌─────────────────────────────┴─────────────────────────────┐
        v                                                           v
  multi_tp_walk (research: simulated bars)          backtest_v2 / live (reported fills)
        └─────────────────────────────┬─────────────────────────────┘
                                      v
                 ┌──────────────────────────────────────────┐
                 │  Parity harness   tests/test_economics_  │  corpus-wide, not 1 fixture
                 │  parity.py -- replay the ledger through  │
                 │  the kernel, assert R agreement to 1e-9  │
                 └──────────────────────────────────────────┘
```

`tests/research/test_multi_tp_walk_parity.py::test_ledger_fixture_levels_reproduce_exactly`
already does this **for one fixture row**. The harness is that test generalised to the
whole ledger, and it becomes the acceptance gate.

---

## Build order

| # | Step | Risk | Gate |
|---|---|---|---|
| 1 | `risk_basis` recorded on `Trade` at plan time; both systems read it. Config-gated, default = today's fill-based denominator. | low | ledger byte-identical with the flag off |
| 2 | Parity harness: replay the existing BNBUSDT + XAUUSD ledgers through `multi_tp_walk`, report R agreement per trade. | none | **it will fail — that failure is the measurement** |
| 3 | Extract `FillModel` from `forward_walk`/`multi_tp_walk`/`backtest_v2`'s slip block. Parity-proved: default arm byte-identical. | medium | harness delta unchanged |
| 4 | Extract `Accountant`. `crt_engine_v2:2511/2538` hardcoded `0.5` reads `execution_planner.partial_tp_fraction` (same value today -- wiring, not behaviour). | medium | ledger byte-identical |
| 5 | Arm DEC-1, then DEC-2, then DEC-3, then DEC-4 — **one at a time**, each with a measured before/after. | high | each delta attributed to one cause |

Step 5 one-at-a-time is not caution theatre. Arm two together and you cannot attribute
the delta, which is exactly how the 17,563-bar divergence became UNATTRIBUTED for a month.

---

## What is still not measured, and should stop being quoted as if it were

`UltronRiskGate` owns economic RR since F-048, and on the active config
`spread_pips = 0.0`, `slippage_pips = 0.0`, guarded by `if total_cost_pips > 0` — **the
cost tax never fires.** `backtest_v2` does not import the gate at all (verified), so
`min_rr_ratio = 1.5` gates nothing in the ledger.

Consequence, stated plainly: **every outcome number in the F-019…F-097 corpus came from
System 1, and no production trade has ever been priced by it.** That is F-010, still open.
Until the parity harness runs, no research R and no ledger R are known to describe the
same trade.

**Objective-function gap (named, not fixed here):** every finding is quoted as expectancy
in R. A desk's objective is expectancy x frequency - cost, then risk-adjusted, then
capacity- and drawdown-constrained. `E = +0.2R` on 13 trades is not a business, and F-001
already says throughput is the binding constraint. The M4 gate has no frequency or
drawdown term. Register as an ontology `UNKNOWN_*` node per S6.6.

---

## Verification

1. Harness (step 2) emits per-trade `rr_research` vs `rr_ledger` and the distribution of
   the delta. **A non-zero delta is the deliverable**, not a failure to suppress.
2. Steps 1/3/4 each assert byte-identical BNBUSDT + XAUUSD ledgers with flags off.
3. DEC-2 arming reports how many founding events the embargo removes (predicted ~24 on the
   XAUUSD 2y corpus) and the occupancy delta.
4. DEC-3 arming reports the TP-fill count change; predicted direction is **fewer TP hits,
   worse expectancy** — if expectancy improves, the implementation is wrong.
5. DEC-4: XAUUSD net R moves by roughly +0.49R per trade vs flat 12 bps (0.5394 -> ~0.048).
6. `pytest tests/test_corpus_gate.py tests/test_resolver_supply.py
   tests/test_crt_state_identity.py tests/research/test_multi_tp_walk_parity.py
   tests/test_cost_model_parity.py` green throughout.

## Out of scope

Parquet (`build_bar_matrix.py:333` still writes outside the governed `parquet_store`).
`warmup_min_days`. Duration-declared indicator periods. The `src/identity/` PK change for
`producer_id: "resolver"`. Committing the staged BC-2/BC-4 set and the untracked identity
files. Market impact / capacity modelling (irrelevant at retail size, and modelling it
badly is worse than omitting it).
