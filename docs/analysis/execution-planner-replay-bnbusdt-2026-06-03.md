# Execution-Planner Replay — BNBUSDT (Selection vs SL/TP attribution)

> Point-in-time analysis (NOT a living doc). PURE MEASUREMENT — no config edit, no promotion, no
> behavior change. · 2026-06-03 · Instrument BNBUSDT on `v4_multi_2026_06` (the promoted config).
> Driver: `scripts/research/execution_planner_replay.py` · Raw: `results/execution_planner_replay/replay_bnbusdt.json`
> Source: additive `RETEST_REPLAY` telemetry (schemas.md §9.4) emitted by `crt_engine_v2.py`.
> Answers the **recommended next experiment** of `gate-contribution-bnbusdt-2026-06-03.md:29`.

## Question

The gate-contribution study showed the entire **+0.584R** edge appears at the RETEST→EXECUTION gate,
but warned that the jump **conflates** (a) *which* retest candles are selected and (b) the CRT
engine's structure-based SL/TP vs a vanilla fixed SL/TP — and "this method cannot separate" them.
This replay separates them with a **2×2** where all four cells are forward-simulated identically
(`analytics.sl_tp_comparator.simulate_exit`, TP2>SL>TP1), so only the varied dimension moves.

## Method (faithful)

- RETEST candidates (selected **and** rejected, with **direction**) come from the new additive
  `RETEST_REPLAY` telemetry — the only source carrying the engine's intended direction (verified:
  `crt_transitions.jsonl` logs `direction:null`).
- **Structure** SL/TP reconstructed with the exact `build_trade` formula (SL anchored to the
  *displacement* candle: `sl = disp_{low|high} ∓ sl_atr_buffer·atr`; intent-specific TP R-multiples).
  Reconstruction reproduces the engine's recorded `sl/tp1` **bit-for-bit** (0/35 mismatch — trust gate).
- **Vanilla** = the `opportunity_scanner` definition (`sl = 1·ATR`, `tp = 2·ATR`, fixed 2R).
- Deterministic; no lookahead (forward candles strictly after the entry index). Selected set == the
  35 real executed trades; rejected set = 99 filtered RETESTs.

## Result — 2×2 expectancy (R, gross/simplified-exit)

| population \ SL-TP | **vanilla** (1·ATR / 2·ATR) | **CRT structure** (displacement-anchored) |
|---|---|---|
| **Selected** (35) | **A** +0.286 (WR 43%, SL-rate 57%, maxDD 6.0R) | **B** +0.357 (WR 57%, SL-rate 43%, maxDD 3.0R) |
| **Rejected** (99) | **C** +0.182 (WR 39%, SL-rate 61%, maxDD 14.0R) | **D** +0.172 (WR 49%, SL-rate 51%, maxDD 13.0R) |

Rejected population = `shadow_advisory_only` 70 + `not_discount_zone` 16 + `not_premium_zone` 13.
*(No session rejects: `v4` already opened all sessions — the Phase-6c lever is spent — so the
currently-rejected RETESTs are the shadow-blocked + zone-blocked ones.)*

## Attribution — the edge is SELECTION, not SL/TP structure

```
observed C→B jump ............... +0.175R   (rejected-vanilla → selected-structure)
  selection effect (avg) ........ +0.145R   [A−C +0.104 (vanilla) ; B−D +0.185 (structure)]
  SL/TP-structure effect (avg) .. +0.031R   [B−A +0.071 (selected) ; D−C −0.010 (rejected)]
  interaction ................... +0.082R   (structure SL/TP helps the selected set, not the rejected)
```

- **Selection dominates ~4.7×.** Choosing *which* RETEST candles trade lifts expectancy +0.10→+0.19R
  regardless of SL/TP method. This is the edge.
- **Structure SL/TP barely moves expectancy** (+0.071R on selected; **−0.010R on rejected**). Its real
  value is **risk-shaping, not alpha**: on the selected set it lifts WR 43%→57% and **halves max
  drawdown (6.0R→3.0R)** via a wider, structure-anchored SL (1.67×ATR vs 1.0×ATR) — but it adds no
  expectancy to candidates selection already rejected.
- **Structure SL/TP does NOT rescue rejected candidates** (D ≈ C). The rejected RETESTs are genuinely
  lower-quality — selection is doing real work, not over-rejecting on a fixable SL/TP artifact.

## Verdict

The RETEST→EXECUTION edge is **created by selection (session/zone/shadow/score), not by SL/TP
placement.** This confirms **F-002** (the edge is the decision *process*) at the gate level and
sharpens the roadmap: the highest-leverage work remains **selection policy** (the proven session
lever, F-003), with structure SL/TP retained for its **drawdown/WR** benefit, not as an expectancy
source. Re-tuning SL/TP is **not** a path to more edge on this evidence.

## Caveats (do not over-read)

- **Gross, not net.** Cells use the simplified `simulate_exit` (no 0.5R trail, no partial-TP, no
  costs), so they read below the real executed **net +0.545R**. The gross→net gap (**+0.188R**) is the
  trail + partial-TP + cost contribution — *constant across cells*, so it cancels in every attribution
  delta. The deltas are the result; the absolute cell levels are not the headline.
- **Currently-rejected population.** On `v4` the rejects are shadow (70) + zone (29), not the historic
  session rejects (already harvested). C/D being gross-positive is consistent with **Phase 6e**: the
  shadow-blocked candidates are marginally positive gross but quality-dilutive at full execution
  (PF 2.54→1.52, maxDD 8.2%) — they were correctly blocked.
- **Live layer still unexercised.** This replays the structure SL/TP (the live mirror) but NOT
  `ExecutionPlannerV1_2` intent/TTL nor `UltronRiskGate` sizing — so **F-010** (live PnL unverified)
  stays OPEN. What this *does* close: the worry that the edge was a lucky-SL/TP artifact — it is not.
- One instrument (BNBUSDT), backtest-only, deterministic single run. The harness takes `--instrument`
  for SOL/ETH/BTC follow-ups.
