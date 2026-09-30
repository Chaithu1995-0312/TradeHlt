# STORY-83.11b: mode C (`decider="resolver"`) founds at the resolver's RETEST

## Context
STORY-83.11 declared `decider="resolver"` but `CRTEngine.__init__` raises `NotImplementedError` (`src/config_layer/crt_engine_v2.py:2910`).
STORY-83.11a (done, `ad088def`) made the resolver reach RETEST without injection, using the engine's own geometry function (`config_layer/retest_geometry.py`).
Result: 1 RETEST entry in one window and 0 in the other, 0 matched against the engine's 4. 83.11b builds the handover so the resolver decides the structure (range, sweep, displacement, retest) and the engine's own soft-conf and risk approval decides execution.
It is a comparison arm, never a parity claim (F-069). Authority: none (§6.5).

Prerequisite from 83.11a's DoD: its results are shown to the user before this starts. This plan is that decision point.

## Decisions taken (user, this session)
1. **Candle source:** widen the engine `candle_buffer` when `decider="resolver"`. Today `cap = atr_period × atr_buffer_multiplier = 14 × 3 = 42` bars (`crt_engine_v2.py:3190`), but an EXPANSION can last up to `max_expansion_age_candles = 495`, so a sweep/displacement candle is usually already evicted. Mode C needs a larger cap. The value is derived from `max_expansion_age_candles` plus the sweep/displacement lead (declared, not a literal).
2. **RETEST install:** extend the transition graph. Add a resolver-founding edge into RETEST from the pre-trade states, declared in the WHO source (`active_models.yaml` `valid_transitions`) and the `VALID_TRANSITIONS` seed (`state_identity.py`). The loader fails closed if YAML differs from code (`state_topology.py`).

## Implementation
1. **Founding sidecar** in `src/charts/resolver_overlay.py` `build_and_cache` (`:70`).
   - In the resolve loop (`:118`), when `state == "RETEST"` and the previous state is not RETEST, snapshot `resolver._memory`: `displacement_direction`, `range_h_ref`, `range_l_ref`, and `sweep_candle_index`, `displacement_candle_index` and `retest_candle_index`.
   - These indices are resolver `candle_index` values, i.e. positions in the post-warmup `timestamps` list (verify off-by-one at `crt_state_resolver.py:765` vs `:2254`/`:2304`). Convert each to a timestamp.
   - Write `founding.csv` next to `states.csv`, one row per entry bar: `timestamp, direction, h_ref, l_ref, sweep_ts, displacement_ts, retest_ts`. `states.csv` is untouched. Add the file name and row count to `meta.json`.
   - Add `load_founding_map(instrument, corpus_sha256)` next to `load_cached_track` (`:151`). It returns `{timestamp: row}`. Missing or stale cache fails closed, with no compute on the read path (same discipline as `load_cached_track`).
2. **Engine seam** in `crt_engine_v2.py`.
   - Remove the `NotImplementedError` (`:2910-2915`). Add `CRTEngine.set_founding_map(map)`. It is run input, not a Setup key. Mode C with no map installed raises at the first `process_candle`.
   - When `decider=="resolver"`, widen the buffer cap (`:3094`, `:3190`).
   - When `decider=="resolver"`, skip `try_expansion_to_retest` at the EXPANSION branch (`:3511`).
   - On a bar present in the map, and only if there is no active trade and `evaluating_soft_conf` is false:
     - Look up the sweep, displacement and retest candles in `candle_buffer` by timestamp. Any missing → reject with `resolver_founding_bar_missing` (event recorded, no state change).
     - Install `active_range`, `sweep_event`, `displacement_candle`, `direction` (resolver ±1 mapped to the `Direction` enum explicitly) and `retest_candle`. Use the new graph edge to move to RETEST via `StateMachine._transition`. Log a distinct event.
     - Then run the same block as `:3512-3519`: `evaluating_soft_conf = True`, `soft_conf_candles = 0`, `BEGIN_SOFT_CONF`. Everything after is unchanged: `approve_with_soft_conf`, `try_retest_to_execution`, `build_trade`.
   - **Reuse, no second copy:** factor the `cached_features` construction and the missing-inputs check out of `try_expansion_to_retest` (`:1800-1860`) into one helper called by both paths. The engine path must stay byte-identical.
3. **Graph edge.** Add the resolver-founding transition to `VALID_TRANSITIONS` and to the WHO `active_models.yaml` `valid_transitions`, plus `event-taxonomy.md` §3 and the state-identity docs. Update the pinned edge-set tests (`tests/test_crt_state_invariants.py` and the topology tests; find them with grep before editing).
4. **Grid arm.** Add `--decider resolver` to `scripts/research/setup_grid_s4.py` (currently hardwired `"decider": "engine"`, `:169`, and the docstring line 9). It builds/loads the founding map and passes it to the engine. Engine-oracle injection stays OFF. The arm is reported as a §7.3 comparison. The runner in `backtest_v2.py` (`:3140`, `decider=self.cfg.decider`) must load the map when `decider=="resolver"`.
5. **Registration.** New/changed scripts follow SITS (§3 item 1b). Non-trivial changes get a §3.3b BUILD_IMPACT_MANIFEST: classify against `docs/governance/change_contracts.json`, then `construction_protocol.py validate-completion <manifest>`.

## Tests (new, short-window fixture only)
- `decider="engine"` events byte-identical (run_id stripped) against the pre-change baseline. Also the existing 279/279 fixture.
- Sidecar unit test: one row per RETEST entry; timestamps round-trip; stale/missing cache fails closed.
- Engine seam: a synthetic map produces RETEST → soft-conf; a missing bar gives `resolver_founding_bar_missing`; a busy engine (trade active) skips founding.
- Graph parity test still passes with the new edge (YAML == code).
- Mode C live check: at least one founding reaches the risk gate, or the run is reported INERT with the reason. Expect INERT or near-INERT, since 83.11a found only 1 resolver RETEST entry and 0 matches.

## Verification
- Working-tree preflight first (`git status`, `git stash list`; concurrent sessions are routine, and `src/runtime/backtest_v2.py` is already modified by another session, so scope any edit there and never `git add -A`). Interpreter `venv\Scripts\python.exe`. Echo the data path and row count before each run.
- Baseline the green floor before editing (`scripts/maintenance/check_governance_invariants.py --all`, known pre-existing reds), then re-run after.
- Short-window fixture only (standing hard constraint); no full-corpus run.
- Report the result faithfully. INERT is a valid outcome.

## Out of scope / risks
- Fixing the resolver's DISPLACEMENT→EXPANSION gap (F-069). If mode C is INERT, that is the finding, not a defect to tune.
- Graph edge is global. The engine path never takes it, but the topology is governed, so expect doc and test churn.
- Widened buffer touches only `decider="resolver"`; `engine` mode cap must stay 42 (asserted by the byte-identity test).
- Session log to `assistant_project.md` and the build_queue status update (`pending` → done, with evidence) at close.
