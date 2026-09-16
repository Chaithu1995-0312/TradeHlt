# TRADE_INTENT_OWNERSHIP_SHADOW — measure option C before authorizing it

`OBSERVATION_ONLY` per `docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`.
**No `src/` edit at all** (the F-067 probe precedent), so ledger identity is structural, not merely
measured. No config, no registry, no promotion, no G001.

## Context

The caller census (`docs/analysis/trade-intent-caller-census-2026-09-16.md`) established that
`ExecutionEngine._derive_trade_intent` reads a CANONICAL vocabulary but is fed a 6-key CRT-local
`cached_features`, overlapping on only `body_ratio` and `double_sweep`. `pullback` is therefore dead
on two independent conditions and `liq_sweep` rests on `double_sweep` alone. Determination was
`TEST / CONTRACT GAP`, with the ownership question left open.

User has now chosen the target architecture — **option C, the F-048 treatment**: delete the CRT
classifier and let `ExecutionPlannerV1_2._derive_intent` own intent — and chosen to **measure it in
shadow first** before any ledger-changing edit.

**The feasibility question is answered: yes, from modules already built.** Nothing new is needed to
produce the data:

| Piece | Already exists | Where |
|---|---|---|
| Whole canonical frame, precomputed up front | yes | `backtest_v2.py:2034` (`enriched_df, self.feature_vectors = pipeline.run()`) |
| Timestamp → row index | yes | `backtest_v2.py:2003` `feature_ts_to_idx` |
| Hardened fail-closed row lookup | yes | T-16 block, `backtest_v2.py:2995-3015` |
| Canonical name→value dict for a bar | yes | `_construction_trace_feature_dict()` `backtest_v2.py:2396` |
| Canonical frame builder for a probe | yes | `crt_episode_number_trace.py:177` `build_ftr_context` / `:223` `full_feature_record` |
| Engine replay with `build_trade` interception | yes | `crt_episode_number_trace.py:305` `replay` / `:370` `build_trade_traced` |
| A working canonical-vocabulary classifier | yes | `ExecutionPlannerV1_2._derive_intent`, `execution_planner.py:331` |

The only true gap is a **seam**, not a module: `process_candle` (`crt_engine_v2.py:2850`) is called
at `backtest_v2.py:2844`, but the canonical row for that same bar is not looked up until `:3015`,
and `build_trade` runs deep inside `process_candle` at `crt_engine_v2.py:3471`. The frame is fully
materialized in `__init__`, so moving a dict lookup earlier introduces no lookahead — the seam is
wiring, and this shadow does not cut it.

Intended outcome: know what option C would actually do to intent labels and TP-multiplier selection
— **including whether it introduces a new reject path** — before anyone authorizes the edit.

## The specific risk this must surface

The two classifiers are not label-compatible:

- CRT returns 4 lowercase outcomes and **always classifies** (fallthrough `reversal`).
- The planner returns 5 UPPERCASE outcomes; its fallthrough is **`UNKNOWN`**, and `plan()` turns
  that into `{"decision": "reject_unknown_intent"}` when the config flag is set
  (`execution_planner.py:233-238`). Its `REVERSAL` is also a different test — EMA-vs-direction, not
  a fallthrough.

So option C can **reject trades the CRT rail currently opens**. That is the headline number.

## Build

One new file: **`scripts/analysis/trade_intent_ownership_shadow.py`**, reusing
`crt_episode_number_trace`'s `build_ftr_context` / `full_feature_record` (canonical row by bar) and
its `replay` + `build_trade_traced` interception pattern rather than re-deriving either.

At every RETEST confirmation (wherever `cached_features` is populated — a larger population than
trade-opens) record a paired observation:

- **Arm CURRENT** — `ExecutionEngine._derive_trade_intent(state.cached_features, cfg.breakout_disp_threshold)`,
  then `tp1_mult = getattr(cfg, f"tp1_atr_multiplier_{intent}", cfg.tp1_atr_multiplier)`.
- **Arm C** — `ExecutionPlannerV1_2._derive_intent(canonical_row, {"selected_direction": +1/-1})`
  with the bar's canonical row, direction mapped from `state.direction`; same `getattr` on the
  lowercased label.

Per record: timestamp, bar index, CRT state, direction, both intents, both multipliers, agreement
flag, and an `is_unknown` flag. Also read and report the active
`execution_planner.reject_unknown_intent` value rather than assuming it.

**Pre-registration (sealed in the script docstring before any result is read), per E-001:**
Arm CURRENT is predicted to be `reversal` on nearly every record; Arm C is predicted to produce a
non-trivial `PULLBACK` share and a non-zero `UNKNOWN` count; n is predicted to be small enough to be
economically INSUFFICIENT.

## Declared limitations — to be written into the artifact, not discovered afterwards

1. **n will be tiny.** XAUUSD on the active config yields ~3 trade-opens and a small retest
   population. This measures **mechanism** (does the label move, does a new reject appear), never
   economics. No expectancy claim is derivable and none will be made.
2. **A label difference is partly definitional, not only coverage.** Arm CURRENT's `rd`/`disp` are
   FM-027/FM-028; Arm C's `retest_depth`/`disp_strength` are FM-021/FM-020 — different quantities —
   and `body_ratio` differs in subject (displacement candle vs current bar). Disagreement must be
   reported as *both* causes, not attributed to coverage alone. (This is the exact trap the census
   already corrected once.)
3. Calling `_derive_intent` directly bypasses `plan()`; declared, since only the classifier is
   under test.
4. XAUUSD only, per standing constraint.

## Outputs

1. `scripts/analysis/trade_intent_ownership_shadow.py` — registered the same turn via SITS
   (`script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`,
   §3.1b). Append a single stub row; do **not** bulk-merge, which would absorb other sessions'
   unregistered scripts.
2. `docs/governance/trade_intent_ownership_shadow.LATEST.json` — immutable artifact (b2a precedent),
   carrying the confusion matrix, the UNKNOWN count, the TP-multiplier change count, and the sealed
   predictions with their pass/fail.
3. `docs/analysis/trade-intent-caller-census-2026-09-16.md` — append a `## 9. Shadow measurement
   (option C)` section. The census is the owning doc; no new doc.
4. `assistant_project.md` SESSION LOG entry.
5. **No finding** unless the mechanism result is decisive. A small-n mechanism observation does not
   earn an F-id; if it lands, it is a Note, not a new row.

## Out of scope

- Cutting the seam. No `process_candle` signature change, no engine setter, no removal of
  `_derive_trade_intent`. Option C is the *measured target*, not this turn's edit.
- Any retrain, promotion, `ACTIVE_VERSION` change, or corpus expansion beyond XAUUSD.

## Verification

1. `venv/Scripts/python.exe -m pytest -q tests/test_breakout_disp_threshold.py tests/test_execution_contract_v1.py`
   — the two floors that pin `_derive_trade_intent`; green proves the probe changed no behaviour.
2. `venv/Scripts/python.exe -m pytest -q tests/test_script_registry.py tests/test_script_matrix_sync.py`
   — SITS registration. `test_script_registry` has 3 pre-existing failures in the baseline; confirm
   they are byte-identical and do not name the new script.
3. `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` — must stay at
   **12 failed / 567 passed**, same twelve names. Any new red is this change's regression.
4. Non-vacuity: assert the probe actually recorded > 0 paired observations and that both arms ran on
   every record — a shadow that silently measured nothing is the F-079/F-083 silent-gap class, and
   must fail loudly rather than report agreement.
