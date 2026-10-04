# Semantic OS v2 — Slice 3 handoff brief: Decision/Execution layer (for Grok)

**Branch:** `semanticos_impl` (slice 2 committed as `0d05bcf`) · **Spec:** [`SEMANTIC_OS_V2_MEANING_PLANE.md`](../governance/SEMANTIC_OS_V2_MEANING_PLANE.md) §14
**Authored by:** Claude (design + registries) · **Implemented by:** Claude (user, 2026-10-02: "You implement" — one-slice exception to O-5) · **Reviewed by:** the user
**Interpreter:** `venv/Scripts/python.exe` (the bare-Python pre-commit hook lacks `jsonschema`)

## 0. Rules (same as slices 1–2)

1. Implement only from the spec, `configs/formulas/concept_contracts.yaml` (records **DEX-01…09**), the REP
   shards in `configs/formulas/representation_registry/` and `terminal_reason_map.yaml`. Never infer meaning
   from a variable name.
2. **Do not edit any existing module** outside `src/semantics/`. Call the authorities named below; copying
   their logic is a defect (I-8). Where none exists, implement the contract rule and test it.
3. **Do not fix divergences** (recorded on each DEX record). Report new ones with file:line.
4. Do not invent ids. Do not bind to a PROPOSED concept.
5. Never delete; explicit `git add` paths only; no shell heredocs to write files; do not commit — Claude
   reviews first.
6. Out of scope: wiring anything into the engine, backtest or live rail; broker lot rounding; running the
   CRT engine or the live rail to obtain verdicts (DEX-04 objects are built from a verdict the caller supplies).

## 1. Already done by Claude (do not change these files)

- `concept_contracts.yaml`: DEX-01…09; TRS-03's D2-2 divergence now reads `decided_in: slice_3` + `resolution`
  (D3-1). Header `slice: 3`.
- `representation_registry/crt_engine.yaml`: `Trade.risk_pct/opened_at/open_candle_index/status/closed_at/
  displacement_origin/pnl`, `events.TRADE_OPENED`, `ExecutionEngine.update_trade` mapped; unmapped shrank to
  `Trade.id/runner_active/partial_pnl/cached_features` (+ the 6 CRTState members).
- New shard `representation_registry/live_rail.yaml` (Ultron, planner; `PortfolioAllocator.allocate` unmapped).
- Spec §14 (D3-1…D3-8, A-10).
- Tests updated: `tests/governance/test_representation_registry.py` (pin), `tests/semantics/trading/test_validator.py`
  (D2-2 settled; the warning test now re-opens it on a copy).

Gate today: `153 passed, 1 skipped`, `validate_all() == []`, no open deferral.

## 2. Package to build — `src/semantics/execution/`

Layering: `geometry → market → trading → execution`; execution may import trading and below, never the
reverse. Every value object carries `concept_id`, `parameterization_id`, `available_at`; absence is `None`,
never a sentinel (I-7). Nothing here changes a thesis, a role or a market object (I-3, I-10).

| Module | Implements | Must call (do not copy) |
|---|---|---|
| `size.py` | DEX-01 `PositionSize(quantity, risk_fraction, equity, equity_basis)`. `quantity = risk_fraction * equity / R`. Raise `ValueError` unless `0 < risk_fraction < 1` (a percent must never pass as a fraction, F-111). None when R is 0 or there is no stop | `semantics.trading.plan.TradePlan` (R) |
| `portfolio.py` | DEX-02 `admit(size, open_positions, *, max_concurrent_positions, max_open_risk, bar) -> Admission(verdict, reason_code)`. FILTERED → `reason_code="portfolio_cap"`. Never trims. Open risk = each open position's entry `risk_fraction` (a stop moved after TP1 does not lower it). Same-thesis positions count like any other | — (contract rule) |
| `fill.py` | DEX-03 `Fill(price, bar, entry_semantics)` from a TRS-04 entry and an ADMITTED admission; None when FILTERED. Entry slippage is not added to the price | `semantics.trading.entry` |
| `approval.py` | DEX-04 `Approval(rail, verdict, reason_code, bar)`. Constructors: `from_crt_reset(reason, bar)` (FILTERED; `reason_code` via `semantics.registry.match_terminal`, which must return class FILTERED, else raise) and `from_ultron(result: dict, bar)` (read the real `UltronRiskGate.evaluate` return keys from source). A FILTERED verdict never touches the thesis | `semantics.registry.match_terminal` |
| `position.py` | DEX-05/06/07. `ExitSchedule(partial_fraction, trail_fraction, tie_break="stop_first")`, `ExitRule(on_invalidation, precedence="after_resting_fills", ttl_bars=None)`, `replay_position(plan, fill, schedule, rule, future_bars, *, invalidation_bar=None, origin_price) -> Position(state, exits, exit_reason, exit_bar)` | `research.oracle.multi_tp_walk.multi_tp_walk` (see §2.1) |
| `carry.py` | DEX-08 `Carry(nights, weighted_nights, carry_price, carry_r, cost_source)` | `research.costs.ComponentCostModel.cost_price` (see §2.2) |
| `result.py` | DEX-09 `PositionResult(gross_r, net_r, walk="bar_replay", basis, cost_model, cost_source, exit_bar)`; identity also carries the DEX-01/06/07 parameterizations | `semantics.trading.cost.component_cost` / `flat_cost`, `carry.py` |

### 2.1 `replay_position` — reuse the walk, do not re-walk

- The resting exits (stop, target 1 partial, trailed runner, target 2, stop_first) **are** `multi_tp_walk` with
  `partial_fraction`, `trail_fraction`, `tie_break=TIE_BREAK_PRODUCTION`, `timeout_pricing=TIMEOUT_MARK_TO_CLOSE`.
- A DEX-07 rule that fires on bar *k* (k = bars after the fill, 1-based) closes at bar *k*'s close **after**
  that bar's resting fills (`after_resting_fills`). Implement it by walking `future_bars[:k]` with
  `max_forward=k`: if the walk exits before or on bar *k* by stop/target, that exit stands; if it returns
  TIMEOUT, the TIMEOUT at bar *k*'s close is the rule exit. **First verify in `multi_tp_walk` source that a
  TIMEOUT on the last bar is priced after that bar's resting fills; if it is not, stop and report.**
- Firing bars: `close_on_invalidation` = the MKT-E10 breach bar (caller passes `invalidation_bar` from
  `semantics.trading.roles`); `close_on_origin` = first bar after the fill whose close is GP-02 BEYOND
  `origin_price` (the MKT-E04 candle open) against the direction (`semantics.geometry`); `ttl_bars` = bar
  `ttl_bars`. The earliest firing bar wins; `hold` never fires on the invalidation.
- `exit_reason` mapping: `STOPPED` → STOP, `TP1_BE_STOP` → TRAIL_STOP, `TP1_TP2` → TARGET_FINAL, rule TIMEOUT →
  INVALIDATION / ORIGIN / TIMEOUT. A walk TIMEOUT at the horizon with no rule leaves the position OPEN
  (`exit_reason` None, no result). `PARTIAL` when the walk reached target 1 and is still open.
- The invalidation is recorded on the thesis by slice-2 code regardless of `on_invalidation`; `position.py`
  only reads it.

### 2.2 `carry.py`

- `nights` = distinct broker-server dates that have bars, after the fill bar's date, up to and including the exit
  bar's date (bar timestamps are server time, F-066; no conversion).
- `weighted_nights` = sum of 3 for a rollover on `triple_swap_weekday` (an argument; `None` = unmeasured), else 1.
- `carry_price = cost_price(exit_kind, direction, nights_held=weighted) - cost_price(exit_kind, direction, nights_held=0)`;
  `carry_r = carry_price / R`. `nights == 0` → a real 0. `nights > 0` with `triple_swap_weekday is None`, or
  `UnmeasuredCostError` from the model → `None` (never 0). `available_at` = exit bar.

## 3. Validator additions — `src/semantics/registry.py`

| # | Check | Invariant |
|---|---|---|
| V-15 ext | The AST scan also covers `src/semantics/execution/` | I-10 |
| V-16 ext | A divergence with `decided_in` must carry a non-empty `resolution` (A-10) | D3-1 |
| V-17 | AST scan of `src/semantics/execution/`: no call to a thesis lifecycle transition and no assignment to an attribute of a `semantics.trading` object (execution never ends a thesis) | I-3 |
| V-18 | Every `lifecycle.exit_reasons` on a DECISION_EXECUTION concept is a list of unique upper-case tokens; DEX-05's list equals `position.ExitReason` members | I-9 |

## 4. Tests — `tests/semantics/execution/`

- One failing-mutation test per V-15 ext…V-18.
- `test_size.py`: quantity × R == risk_fraction × equity; percent 1.0 raises; R 0 → None; `equity_basis` changes the id.
- `test_portfolio.py`: count cap and risk cap each FILTER with `portfolio_cap`; never trims (quantity unchanged
  or FILTERED); a second position of the same thesis is admitted while the first is open; a stop moved after TP1
  does not free risk.
- `test_fill_approval.py`: FILTERED admission → no fill; `from_crt_reset` on an off-session reason → FILTERED, on a
  MARKET reason → raises; a FILTERED approval leaves the thesis ACTIVE.
- `test_position.py`: under `hold` and no TTL the result equals `multi_tp_walk` for STOPPED / TP1_BE_STOP / TP1_TP2
  paths; `close_on_invalidation` and `close_on_origin` close at the firing bar's close; a bar that hits TP1 and
  fires the rule books the partial, then closes the runner at the close; a wick through the origin that closes back
  does not fire; `hold` with an invalidation keeps the position open and the thesis FAILED; the earliest rule wins;
  each `on_invalidation` value gives a different id.
- `test_carry.py`: Fri→Mon over a weekend = 1 night when only Monday has bars; triple weekday counts 3; unmeasured
  swap with a night → None; same-day exit → 0; credit swap adds nothing (cost model rule).
- `test_result.py`: gross = Σ fraction × move / R; net subtracts cost for the actual final exit kind (TRAIL_STOP and
  STOP are stop exits) and carry; net is None when carry is None; open position → None.
- Availability (I-6): no execution object has `available_at` earlier than the bar of any input it uses.

`tests/semantics/` is already on the GREEN_FLOOR; no floor-list edit is needed.

## 5. Done means

- `venv/Scripts/python.exe -m pytest tests/semantics tests/governance/test_concept_contracts.py tests/governance/test_representation_registry.py tests/governance/test_terminal_reason_map.py -q` green, no warnings from V-16.
- `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all`: only the 7 pre-existing reds
  (schema-version census, model-path literals ×3, script-registry grandfather ×2, corpus-read lint).
- `git diff --stat` touches no pre-existing `src/` module except `src/semantics/registry.py`, and none of Claude's
  registry or spec files.
- Report: files, test output, floor result, new divergences (file:line), questions. Do not commit.
