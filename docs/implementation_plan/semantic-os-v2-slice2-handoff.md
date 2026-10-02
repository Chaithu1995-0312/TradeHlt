# Semantic OS v2 — Slice 2 handoff brief: Trading layer (for Grok)

**Branch:** `semanticos_impl` (slice 1 committed as `abc641d`) · **Spec:** [`SEMANTIC_OS_V2_MEANING_PLANE.md`](../governance/SEMANTIC_OS_V2_MEANING_PLANE.md) §13
**Authored by:** Claude (design + registries) · **Implemented by:** Grok · **Reviewed by:** Claude against the concept contracts (no separate audit this slice)
**Interpreter:** `venv/Scripts/python.exe` (the bare-Python pre-commit hook lacks `jsonschema`)

## 0. Rules (same as slice 1)

1. Implement only from the spec, `configs/formulas/concept_contracts.yaml` (records **TRS-01…08**), the
   REP shards in `configs/formulas/representation_registry/` and `terminal_reason_map.yaml`. Never infer
   meaning from a variable name.
2. **Do not edit any existing module.** Call the authorities named below; copying their logic is a defect (I-8).
   Where no callable authority exists, implement the contract rule and add a test that compares it with
   the engine on a synthetic state (that test is the guard against a drifting copy).
3. **Do not fix divergences** (they are recorded in each TRS record). Report new ones with file:line.
4. Do not invent ids. Do not bind anything to a PROPOSED concept or value (an M15 objective is PROPOSED).
5. Never delete; explicit `git add` paths only; no shell heredocs to write files; do not commit — Claude
   reviews first.
6. Out of scope: fills, position lifecycle, approval, sizing, the exit schedule (partial fractions, stop
   moves after TP1) — all slice 3 (D2-6).

## 1. Already done by Claude (do not change these files)

- `concept_contracts.yaml`: TRS-01…08; MKT-E09 renamed `retest_touch` (alias `retest_entry`).
- `representation_registry/crt_engine.yaml`: `Trade.direction/entry_price/sl_price/tp1_price[intent]×4/tp2_price`
  mapped; the other 11 `Trade.*` fields in `unmapped`.
- `representation_registry/parent_crt.yaml`: `ObjectiveStatus` ×4 → TRS-02; `unmapped` now empty.
- New shards `research_walks.yaml` (forward_walk, multi_tp_walk → TRS-08) and `research_costs.yaml`
  (ComponentCostModel, CostModel → TRS-07).
- Spec §12 A-7/A-8, §13 D2-1…D2-8.

`validate_all()` is clean on these files today, and Claude has already updated the unmapped pin in
`tests/governance/test_representation_registry.py` (11 `Trade.*` keys; parent list empty; the two new
producers pinned empty). All existing tests are green at handoff.

## 2. Package to build — `src/semantics/trading/`

Every value object carries `concept_id`, `parameterization_id`, `available_at`; absence is `None` /
`present=False`, never a sentinel (I-7). Roles never call `Level.with_status` or change any market object (I-10).

| Module | Implements | Must call (do not copy) |
|---|---|---|
| `thesis.py` | TRS-01 `Thesis(direction, founding, sweep_bar, born_at = MKT-E04 bar, available_at = born_at, invalidation: Invalidation)`. Constructor from a slice-1 sweep `MarketEvent` + the displacement bar; **no thesis without a displacement** (returns None). Lifecycle ACTIVE → FAILED (TRS-03) / SPENT (MKT-E11) / EXPIRED (MKT-E12) | `semantics.market.events` (`sweep`, `retrace_breach`, `extension_reach`, `clock_rollover`), `semantics.geometry.directional_impulse` |
| `roles.py` | TRS-03 `Invalidation(retrace_fraction)` evaluated as MKT-E10 on the MKT-L02 retracement of the displacement move. TRS-02 `Objective(scope="parent_range", status, target)` from `resolve_objective`; maps `ObjectiveStatus` → role status; the level object is never modified | `semantics.market.levels.retracement`, `semantics.market.events.retrace_breach`, `config_layer.htf_state.resolve_objective` |
| `entry.py` | TRS-04 `Entry(price, bar, entry_semantics, available_at)`. `resting_order`: price = retest (MKT-E09) bar close, bar = that bar. `approval_bar_legacy` is accepted as input but the object carries `divergence="TRS-04 approval_bar_legacy"` | — (contract rule) |
| `stop.py` | TRS-05 `Stop(price, anchor, buffer_atr)` | `ExecutionEngine(config, sl_anchor=…, target_policy=…).stop_price(state)` from `config_layer.crt_engine_v2` with a minimally populated `EngineState` (`displacement_candle`, `direction`, `atr_abs`, `sweep_event`). If that cannot be done without editing the engine, **stop and report** — do not copy |
| `target.py` | TRS-06 `Target(price, ordinal, target_policy, r_multiple, intent)`. `fixed_r`: entry ± r_multiple·R. `structural_tp2`: the founding range's opposite edge as a TARGET role; reject (None + reason) if behind entry or closer than 1R | intent: `CRTEngine._derive_trade_intent` (static). Arithmetic is the contract rule: add a test comparing your targets with `ExecutionEngine.build_trade` on a synthetic state |
| `cost.py` | TRS-07 `Cost(cost_r, cost_model, cost_source)`; None when the model's status is UNKNOWN (never 0) | `research.costs.ComponentCostModel.cost_r`, `research.costs.CostModel.cost_r` |
| `outcome.py` | TRS-08 `Outcome(gross_r, net_r, walk, basis, cost_model, walk_params, exit_bar, available_at = exit_bar)`; `net_r = gross_r - cost_r`; `parameterization_id` over walk, basis, cost_model, walk_params | `research.measurement.forward_walk.forward_walk`, `research.oracle.multi_tp_walk.multi_tp_walk` |
| `plan.py` | `TradePlan(thesis, entry, stop, targets, objective=None)`. **I-11:** construction raises if the thesis has no invalidation or the plan has no stop. R = abs(entry − stop); inverted stop → no plan | — |

## 3. Validator additions — `src/semantics/registry.py`

| # | Check | Invariant |
|---|---|---|
| V-13 | Every concept of kind THESIS has `roles.invalidation` (a concept of kind INVALIDATION) and `roles.stop` (kind STOP); every id in `roles` exists | I-11 |
| V-14 | Every REP of an OUTCOME concept carries `walk` and `basis`; `basis: gross` requires `cost_model: none`; `basis: net` requires a cost model other than `none` | I-15 |
| V-15 | AST scan of `src/semantics/trading/`: no `.with_status(` call and no assignment to a `.status` attribute | I-10 |
| V-16 | Deferred decisions: a divergence with `decide_in: slice_3` is an **error** once any ACCEPTED concept of layer `DECISION_EXECUTION` exists. Also expose `open_deferred_decisions()` and add a test that emits a `UserWarning` listing each open one on every run (loud until settled) | D2-2 |
| V-7 fix | When a REP value is a config reference, the legacy-value check uses the **resolved** value (still requires `divergence_ref`) | I-2 |
| V-10 ext | `crt_engine.yaml` covers every field of `config_layer.crt_engine_v2.Trade` (`dataclasses.fields`) in representations or unmapped. A `Trade.tp1_price[intent]` key counts as covering `Trade.tp1_price` | coverage |
| V-1 ext | An alias equals no concept's `canonical_name` and no other alias | identity |
| domain | `_in_domain` supports `str` (any non-empty string) and `mapping` (a dict) | — |

## 4. Tests — `tests/semantics/trading/` + floors

- One failing-mutation test per new check V-13…V-16, the V-7 fix, the V-10 extension and the V-1 extension.
- `test_thesis.py`: no displacement → no thesis; thesis born on the MKT-E04 bar (not the sweep bar); FAILED on MKT-E10,
  SPENT on MKT-E11, EXPIRED on MKT-E12; invalidation never closes anything (it only sets thesis status).
- `test_roles.py`: objective ACHIEVED at `close == target` (GP-03 inclusive), INVALIDATED needs a close
  strictly beyond (GP-02); the same level is the objective of a LONG and the invalidation edge of a SHORT, and
  its `status` is unchanged after both (I-10).
- `test_plan.py`: I-11 (missing invalidation or stop raises); inverted stop → None; R; stop equals
  `ExecutionEngine.stop_price` for both anchors; targets equal `build_trade` for `fixed_r` and `structural_tp2`
  (including both rejection reasons); intent picks the matching r_multiple.
- `test_entry_cost_outcome.py`: resting_order entry bar/price; legacy carries its divergence; cost None
  when UNKNOWN; outcome ids differ when walk, basis, cost_model or any walk_param differs (I-15); gross with a
  cost model and net without one are both refused.
- Availability (I-6): no trading object has `available_at` earlier than the bar of any input it uses.

`tests/semantics/` is already on the GREEN_FLOOR and `src/semantics/` is already governed; no floor-list edit
is needed.

## 5. Done means

- `venv/Scripts/python.exe -m pytest tests/semantics tests/governance/test_concept_contracts.py tests/governance/test_representation_registry.py tests/governance/test_terminal_reason_map.py -q` green.
- `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all`: only the 7 pre-existing
  reds (schema-version census, model-path literals ×3, script-registry grandfather ×2, corpus-read lint).
- `git diff --stat` touches no pre-existing `src/` module and none of Claude's registry files.
- Report: files, test output, floor result, new divergences (file:line), questions. Do not commit.

## 6. Review fixes (Claude review, 2026-10-02) — round 2

Claude amended TRS-03/06/07/08 and spec §12 A-9 (do not edit those). Your three questions are answered there:
the invalidation role stays available on the MKT-E04 bar; the body/inclusive engine retrace is a TRS-03
divergence (your sweep→close move is now the contract, user decision); `forward_walk_oco` is removed (user).

| # | File | Fix | Test |
|---|---|---|---|
| R-1 | `outcome.py`, `cost.py` | **Defect.** A net outcome subtracts a cost computed before the walk with a caller-chosen `exit_kind`. For `basis: net`, take the cost model and `cost_source` instead of a `Cost`; walk first; stop exit = `outcome == "SL_HIT"` (forward_walk) or `research.oracle.multi_tp_walk.is_stop_exit(outcome)`; then call `component_cost` / `flat_cost`. A component cost's `available_at` is the exit bar; flat bps stays on the plan bar. | A stop exit and a target exit give different component `cost_r`, each equal to `ComponentCostModel.cost_r` for that exit kind; component `available_at == exit_bar` |
| R-2 | `outcome.py` | The outcome `parameterization_id` includes `cost_source` when `basis: net` | two calibrations → two ids |
| R-3 | `outcome.py` | `_json_params`: a dataclass value (SEM-016 `AdverseFill`) enters the identity as `{"__type__": class name, **dataclasses.asdict(v)}`; the walk receives the original object | `AdverseFill(stop_slippage=0.0)` vs `0.09` → different ids, and the walk result changes on a stop exit |
| R-4 | `outcome.py`, `test_entry_cost_outcome.py` | Remove `forward_walk_oco` from `_WALKS`, the call branch and `_exit_bar`; remove `test_unfilled_oco_is_absence` (the walk no longer belongs to TRS-08) | `measure_outcome(walk="forward_walk_oco")` raises |
| R-5 | `target.py` | `structural_tp2_target` leaves `r_multiple` out of its identity | two nominal multiples → same id |
| R-6 | `test_roles.py` | I-10: one level is the objective of a LONG and the invalidation edge of a SHORT; its `status` is unchanged after both | — |
| R-7 | `src/semantics/__init__.py:8` | Update the stale "trading layer is a later slice" docstring line (allowed edit) | — |

Same rules (§0) and done-means (§5). Report files, tests, floor, questions. Do not commit.
