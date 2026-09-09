# Decision Atlas — a transition-grained warehouse over the envelope streams

## Context

Every measurement in this chain has pushed the unit of analysis down one level. 673 vs 75
EXPANSION bars looked like a state disagreement; episode decomposition showed it was 4 vs 1
*entry decisions* with everything after them being dwell. P-001 then showed the pooled bar-level
statistic reverses sign between its own two largest episodes. The conclusion is structural: **the
bar is not the unit, and occupancy is not the unit — the transition decision is.**

This builds that as a queryable object: a small star schema in Parquet, queried with DuckDB,
centred on `transition_decision`. It replaces bespoke per-question scripts with a table you can
ask new questions of, and it makes the corpus a parameter rather than a rewrite.

**Two corrections to the design doc I sent you, both found while verifying it:**

1. **The "blocking finding" was wrong.** I claimed direction was emitted for only 4 of 199
   transitions and that an envelope schema change was the prerequisite. `crt_direction` is
   already emitted (LONG 1012 / SHORT 355 / NONE 855) — in `bar_structure_snapshot`, produced by
   the *same run*, joinable on `(run_id, bar_index)`. I had read only one of the two streams.
   **No `src/` change is required.** So are `parent_crt_state`, `parent_bias`, `objective_status`,
   `htf_state`, `htf_candle_id` and the full SMC context — 122 fields.
2. `htf_id` *is* accepted by `emit()` and silently discarded (never written to the envelope row).
   Real, but now irrelevant: `htf_candle_id` is on the sibling stream. Noted, not fixed here.

**Scope decision (yours):** build on the existing 2,300-bar window streams already on disk, not a
fresh full-corpus run. Corpus stays a CLI parameter so re-pointing at the 47k corpus is one flag.
**Consequence, stated plainly:** this window has 4 EXPANSION decisions, so nearly every atlas cell
will report `INSUFFICIENT` and the ranking will be E4-concentrated. The machinery is the
deliverable here, not the answer.

**Claim class (yours):** descriptive + power labels. No p-values, no verdicts, no significance
testing.

## What already exists and must be reused

| Need | Reuse | Where |
|---|---|---|
| Timestamp join + float32-relative OHLC guard | `join_and_verify()` | `scripts/analysis/p001_excursion_probe.py` |
| Uncapped excursion via governed kernel + naive twin | `excursion()` | same file |
| Episode segmentation, tail/run concentration | `_runs()`, `episode_inventory()`, `_tail_concentration()` | same file |
| Direction + all context | `crt_direction`, `parent_crt_state`, `objective_status`, `htf_state` | `logs/dual_construction_v2_envelope_safe/XAUUSD_bar_structure.jsonl` |
| Engine/resolver state, transitions, sites, L2 map | v2.0.0 envelope | `..._crt_construction.jsonl` |
| Query engine | duckdb 1.5.5, pyarrow 25.0.1 | already installed |

Do **not** route this through `src/utils/parquet_store.py` — that is a 1:1 JSONL *mirror* with a
log-fidelity contract. These are derived relational tables, a different object.

## The grain

`episode` = maximal contiguous occupancy run of one engine state ⇒ **every transition opens
exactly one episode**, and E1–E4 are simply the four EXPANSION-state episodes. One vocabulary,
not two.

```
transition_decision  (fact, ~199 rows)
  ├─ opens →      episode        1:1
  ├─ measured by → excursion     1:3 (H20/H40/H80)
  └─ occupies →   envelope_bar   1:many (the dwell bars)
```

### `to_state` is the wrong key — the decision type is `(from_state, to_state, reason_family)`

Measured: 11 distinct types. `RANGE→SWEEP` 72 · `SWEEP→RANGE HTF changed` **58** ·
`RANGE→RANGE HTF changed` **38** · `SWEEP→DISPLACEMENT` 13 · `DISPLACEMENT→RANGE retrace` 5 ·
`DISPLACEMENT→EXPANSION` 4 · `DISPLACEMENT→RANGE HTF` 3 · `EXPANSION→RETEST` 2 ·
`RETEST→RANGE off_session` 2 · `DISPLACEMENT→RANGE extension` 1 · `EXPANSION→RANGE retrace` 1.

Two facts the schema must carry: **~99 of 199 are HTF-clock resets, not market events**, and
**38 are `RANGE→RANGE` self-transitions** where the state does not change at all. A ranking over
all 199 would be half calendar bookkeeping. `decision_class ∈ {MARKET, CLOCK, SESSION}` and
`is_self_transition` exist so the default ranking can exclude them explicitly rather than by
someone remembering to.

## Tables (`results/decision_atlas/*.parquet`)

- **`transition_decision`** — `decision_id, run_id, ts, bar_index, from_state, to_state,
  reason_raw, reason_family, decision_class, is_self_transition, direction, direction_source,
  episode_id, bars_to_prior_decision`
- **`episode`** — `episode_id, state, entry_decision_id, entry_ts, exit_ts, bars, direction,
  net_atr, right_censored, resolver_first_agree_ts, resolver_agree_bars, resolver_lag_bars`
- **`envelope_bar`** — 2,222 rows: `run_id, ts, bar_index, engine_state, resolver_state, agree,
  projected_site, live_atr, ohlc, episode_id, bars_since_entry` + context (`parent_crt_state`,
  `parent_bias`, `objective_status`, `htf_state`, `htf_candle_id`)
- **`excursion`** — `decision_id, horizon, up_exc, down_exc, fav_exc, adv_exc, fav_minus_adv,
  reach, truncated, spans_gap, bars_available`

`bars_since_entry` is what makes "dwell bars are not observations" queryable: any honest
aggregate filters `bars_since_entry = 0` or groups by `episode_id`.

`fav_exc`/`adv_exc`/`fav_minus_adv` are **NULL when `direction` is NULL or NONE** — never
defaulted to the up-side. For `→ RANGE` terminations there is no side to be favourable to; those
get `reach` plus excursion measured in the *ending* episode's direction, which answers a
different question ("did the engine give up before or after the move") and must never share a
ranking column with continuation.

## Cross-checks that must pass before any table is written

These are already-measured invariants; if the builder disagrees with them, the builder is wrong.

1. `199` transitions total; `0` bars carrying >1 hop.
2. `crt_state_changed == True` on **161** bars, and `199 − 161 == 38` == the `RANGE→RANGE`
   self-transition count. (Independent confirmation of the self-transition finding.)
3. `crt_action` counts corroborate transition targets: `SWEEP_DETECTED` 72, `DISPLACEMENT_CONFIRMED`
   13, `EXPANSION_CONFIRMED` 4, `RETEST_CONFIRMED` 2.
4. Envelope LIVE rows `2222`; `bar_structure` non-warmup rows `2222`; join unmatched `0`,
   OHLC mismatches `0` under the relative tolerance.
5. Engine EXPANSION episodes `4`, resolver EXPANSION episodes `1`, resolver ⊂ engine `True`.
6. `crt_direction` at the 4 EXPANSION entries agrees with the reason text and the entry-candle
   sign, 4/4 (already verified two ways).

## Ranking, with the controls that make it readable

Default query: top-N `MARKET` decisions by `fav_minus_adv` at H20, excluding self-transitions
and NULL-direction rows. Every ranking result must also report:

- **episode concentration** — how many *distinct* `episode_id`s the top-N came from. If it is 2,
  the ranking is a fact about two events.
- **overlap** — `bars_to_prior_decision`; decisions minutes apart share ~85% of an H20 window and
  are one observation twice.
- **base rate** — per-state rates with n, and `power: INSUFFICIENT` where n < 30, which on this
  window is every state except RANGE and SWEEP.

## Files

- `scripts/analysis/build_decision_atlas.py` — builder (read-only over the two JSONL streams →
  four Parquet files). Imports the reusable functions from `p001_excursion_probe.py` rather than
  copying them.
- `scripts/analysis/query_decision_atlas.py` — thin DuckDB query surface: the default ranking
  plus the named questions (E4-like events, EXPANSION entries, resolver lag, top disagreement
  episodes). `read_parquet` directly; no `.db` file, no persistent state.
- Both need SITS registration in the same turn (`script_census.py --write-stubs` →
  `seed_script_registry.py` → `generate_script_matrix.py` → grandfather pin resync), else the
  GREEN_FLOOR coverage test fails. Mechanical, one command chain.

## Verification

1. All six cross-checks above pass; builder aborts on any mismatch rather than writing.
2. Row counts: `transition_decision` 199, `episode` 199, `envelope_bar` 2222, `excursion` 597.
3. `episode` rows whose `state == 'EXPANSION'` reproduce E1–E4 exactly — bars 49/2/252/370, net
   ATR +4.23/−0.57/−2.20/+58.72, E4 `right_censored = True`, resolver lag 295 on E4 and NULL
   elsewhere.
4. Direction-normalized `fav_minus_adv` at H20 reproduces E1 −0.142, E3 −0.536, E4 +2.058.
5. DuckDB round-trip: the four named queries run and return without error.
6. Artifact carries no p-value/CI/verdict key (assert, as in P-001).
7. `pytest tests/test_script_registry.py tests/test_script_matrix_sync.py -q` green.

## Out of scope

- Any `src/` change, any config change, any envelope schema change — none is needed.
- Significance testing, economic claims, G001, promotion, new `F-*`/`SEM-*` ids.
- The full 47k corpus run (deferred by your decision; one CLI flag when wanted).
- Fixing the discarded `htf_id` parameter in `emit()` — noted, not this task.
