# STORY-83.11b — mode C (`decider = "resolver"`): design recap

## Context
STORY-83.11 shipped the Setup overlay's `target_policy` and `trade_ttl_candles`. Its third key,
`decider`, can be declared, but `CRTEngine(decider="resolver")` raises `NotImplementedError`. The
reason is a gap found during 83.11: mode C needs the resolver's founding objects, and the cache it
was meant to read (`states.csv`) stores only `[timestamp, state]`.

Mode C was meant to answer one question: **what if the resolver, not the engine's state machine,
decides when a trade is founded**, with the engine keeping the trade's geometry (stop and targets)
and its exits? Spec: `docs/implementation_plan/setup-overlay-spec-2026-09.md` §5. Decisions already
made in §10:
- Q4a: offline cached resolver output, not an in-walk call.
- Q4b: a per-arm switch.
- Q4c: rows are joined by same-bar timestamp.
- Engine-oracle injection is OFF (hard constraint).

## The design as specified (§5)
1. The engine keeps running its own state machine for resets and exits, but it no longer founds
   trades. Founding happens only when the cached resolver track says EXECUTION on this bar.
2. At that bar, the engine builds the trade with its existing `ExecutionEngine.build_trade`. The four
   objects it needs are handed over from the resolver:

| Object | Resolver memory today | Engine field |
|---|---|---|
| active range | `range_h_ref` / `range_l_ref` | `state.active_range` |
| sweep candle | `sweep_candle_index` (an index only) | `state.sweep_event.candle` |
| displacement candle | `displacement_candle_index`, `_close`, `_direction` (±1) | `state.displacement_candle`, `state.direction` |
| retest candle (this is the entry) | `retest_candle_index` (an index only) | `state.retest_candle` |

   These fields stay engine-side: `atr_abs`, `cached_features`, `risk_score`.
3. Mode C is **not parity-tested**. F-069 found the two constructions diverge, so its output is a
   §7.3 comparison arm.

## Blocker found (RUNTIME, verified today)
The STORY-83.10 full-corpus resolver track (`results/wpj/after/states.csv` in the wpJ worktree,
47,197 bars) contains no RETEST or EXECUTION rows:

| State | Bars |
|---|---|
| RANGE | 21,745 |
| SWEEP | 15,186 |
| EXPANSION | 7,092 |
| DISPLACEMENT | 3,127 |
| SHADOW_PENDING | 47 |
| RETEST | **0** |
| EXECUTION | **0** |

**Why.** Entering RETEST requires `sweep_detected = SweepDetected` on the same bar as
`retest_flag = RetestActive`, while memory is in EXPANSION (`market_crt_states.yaml:131-141`,
`crt_state_resolver.py:1724-1735`). By EXPANSION, the sweep happened bars earlier. This matches the
note already recorded at `market_crt_states.yaml` (Phase E1): "the RETEST branch is never entered on
this corpus regardless of this value." Earlier F-069 runs did reach RETEST, but only with
engine-oracle injection, which mode C forbids.

**Consequence.** Mode C, implemented exactly as specified, founds **0 trades** on XAUUSD. Building
the cache extension first would ship an empty arm.

## Pieces that hold under any founding choice
- **Founding sidecar, not a wider `states.csv`.** Next to `states.csv`,
  `charts/resolver_overlay.build_and_cache` writes one row per founding bar: `timestamp`,
  `direction`, `h_ref`, `l_ref`, and the TIMESTAMPS of the sweep, displacement and retest bars.
  Timestamps are used instead of resolver indices, because the resolver indexes the post-warmup
  enriched frame while the engine counts 1-based over the full stream. Joining by timestamp is the
  Q4c decision. The existing 2-column `states.csv` stays byte-identical, which keeps STORY-83.10's
  parity intact.
- **Engine side.** `CRTEngine` receives the sidecar as a `{timestamp: FoundingSnapshot}` dict.
  - With `decider="resolver"`, the engine's own `try_retest_to_execution` → `build_trade` founding
    path is skipped.
  - On a sidecar bar, the engine takes each handed-over candle from its own `candle_buffer` by
    timestamp, sets the four fields on a copy of state, and calls the unchanged `build_trade`.
  - If a timestamp is missing from the buffer, the founding is rejected with a reason
    (`resolver_founding_bar_missing`). It is never guessed.
- **`risk_score` / `cached_features`.** When the engine is not in RETEST, these are stale or `None`,
  and `build_trade` then falls back to `risk_pct=0.005`. This is disclosed per arm (a count of
  fallback-sized trades), not fixed.
- The resolver cache is built once per corpus and per variant, and passed to every mode-C arm
  (Q4a cost intent).

## The decision that is yours
Which resolver event founds the trade? See the question below.

## Verification (after the choice)
- Measured on the short-window fixture first (standing hard constraint).
- Mode C arm must be live (§9.2 check 4): it must found ≥1 trade, or be reported INERT with the
  reason.
- `decider="engine"` stays byte-identical to today, checked on the events stream with `run_id`
  stripped.
- `states.csv` stays byte-identical, and the sidecar is additive.
- Every founding carries the resolver's stamps, plus a count of trades that fell back to
  `risk_pct=0.005`.
