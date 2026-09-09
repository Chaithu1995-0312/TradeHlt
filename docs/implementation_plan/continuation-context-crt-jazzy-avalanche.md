# Plan: Shadow Cross-Range Restoration Telemetry Probe (measurement only)

## Context

The CRT shadow-restoration investigation established that `try_shadow_pending_to_expansion`
(`src/config_layer/crt_engine_v2.py:1070-1094`) can restore a `displacement_candle` that was
stashed under a *different* HTF range than the one currently active
(`state.pending_displacement_source_htf` vs `state.active_range.htf_candle_id`) — "cross-range
displacement resurrection." Two observed instances (n=2) of this coincide with an "inverted SL"
trade rejection in `ExecutionEngine.build_trade` (`crt_engine_v2.py:2339-2444`), but n is far too
small to mean anything, and no existing telemetry surface can answer the question at scale:

- The transient `action["shadow_source_htf"]` field (set at `crt_engine_v2.py:3089`) is never
  persisted to any JSONL.
- The inverted-SL guard (`crt_engine_v2.py:2379-2390`) returns `None` with only a `log.warning` —
  no `EngineEvent`, no integrity event, no telemetry candidate-closure. It is invisible to the
  backtest driver: `action["action"]` stays `"NONE"` (default at line 2878) because the
  `if trade:` block that would set `"TRADE_OPENED"` is skipped.
- Existing lifecycle telemetry's `shadow_used` flag doesn't distinguish same-range from
  cross-range, and its 6 observed `shadow_used=True` rows all terminated in
  `RESET_RETRACE`/`RESET_EXTENSION`, not inverted-stop — so it can't proxy for either bucket.

**Goal of this plan**: design + implement a read-only measurement probe (no `src/` edit, no
behavior change) that produces real counts for:
1. same-range vs cross-range restoration frequency, and
2. inverted-stop vs trade-opened vs reset-before-execution outcome, within each bucket.

No finding is registered, no config is touched, no G001 claim is made. This is evidence
collection only, per the Authority Ladder (§6.5) — a probe reports counts, it does not grant
authority to change anything.

User decision (asked and confirmed): build this as a **standalone external probe script**
(no source edit at all), not a permanent addition to `crt_engine_v2.py`. If the resulting counts
show something worth acting on, promoting to permanent instrumentation is a separate, later,
explicitly-authorized decision — it is out of scope here.

## Precedent this follows

`scripts/analysis/soft_conf_ema_double_update_probe.py` (cited by F-067) is the established
template for exactly this kind of question: drive the real `CRTEngine`/`BacktestRunner` (never
hand-roll a candle loop), monkeypatch a small number of class methods **in-process only**, always
call the original and return its real, unmodified result, restore originals in `finally:`. Output
goes to `results/analysis/*.LATEST.json` (+ `.LATEST.md`), never to `logs/*.jsonl`. A companion
`tests/test_*_probe.py` re-derives the probe's own bucketing logic independently as a
self-consistency floor. The script must be SITS-registered (`category="DIAGNOSTIC"`,
`ttl_days=90`) via a curated overlay in `scripts/governance/seed_script_registry.py` — confirmed
precedent entries at lines ~721-732 (`rr_confidence_probe`, F-044) and ~764-780
(`soft_conf_ema_double_update_probe`, F-067).

## Verified source facts this design depends on

- `ExecutionEngine` class at `crt_engine_v2.py:2278`; `build_trade` at `:2339-2444` — confirmed
  (by direct read) to have **exactly 4 distinct `None`-return causes**, in this order:
  missing `active_range`/`sweep_event` (2342-2344) → missing `displacement_candle` (2357-2359) →
  `direction == NONE` (2371-2373) → inverted-SL guard, LONG (2379-2384) or SHORT (2385-2390).
  Nothing after the guard returns `None` — every remaining path builds and returns a `Trade`.
  This means a `build_trade`-return-value classifier can distinguish "inverted SL" from every
  other `None` cause with certainty, no log-text matching required.
- `state.pending_displacement_source_htf` is stamped in `reset_to_range` (`:1891-1893`) from
  `state.active_range.htf_candle_id` **after** the caller (`process_candle:2888-2890`) has already
  reassigned `active_range` to the post-reset range — a pre-existing imprecision in what this
  field actually records. Not something to fix here; just a caveat to carry into the artifact.
- `try_shadow_pending_to_expansion` does not clear `pending_displacement_source_htf` — the caller
  clears it only on success, at `crt_engine_v2.py:3109`, *after* reading it into `action[...]` at
  `:3086/3089`. So a wrapper reading `state.pending_displacement_source_htf` at the *entry* of
  `try_shadow_pending_to_expansion`, before calling the original, sees the correct pre-restore
  value.
- Single CRT episode per engine instance at a time (`current_state` is one enum on one
  `EngineState`); `reset_to_range` unconditionally returns to `RANGE` before a new episode can
  begin. A single-slot "open episode" correlator on the probe side is safe for a single-instrument
  run (this probe targets XAUUSD only, matching the repo's existing XAUUSD-only research
  convention).
- Existing tests that must keep passing unmodified since no `src/` line changes:
  `tests/test_crt_adversarial_closure.py:240-248` (`_came_from_shadow` cleared by
  `reset_to_range`), `tests/Grok/test_A_crt_journeys.py` (`test_shadow_collapse_is_two_legal_hops_not_one`,
  `test_shadow_collapse_restores_older_displacement_than_confirming_bar`). Since this probe makes
  zero `src/` edits, none of these are at risk — listed only for completeness.

## Design

### New file: `scripts/analysis/shadow_cross_range_restoration_probe.py`

Imports `CRTEngine` / `EngineState` / `StateMachine` / `ExecutionEngine` / `Direction` from
`config_layer.crt_engine_v2`, and drives the real `BacktestRunner`/`CandleLoader` from
`runtime.backtest_v2` over the XAUUSD M15 corpus, exactly as the precedent script does.

**Patch 1 — `StateMachine.try_shadow_pending_to_expansion`** (Bucket A: same/cross-range capture).
Read `shadow_source_htf = state.pending_displacement_source_htf or None` and
`active_range_htf = state.active_range.htf_candle_id if state.active_range else None`
**before** calling the original. Call the original, and only on success (`ok is True`) classify:

```
if not shadow_source_htf or not active_range_htf:  bucket = "UNKNOWN"
elif shadow_source_htf == active_range_htf:         bucket = "SAME_RANGE"
else:                                                bucket = "CROSS_RANGE"
```

Append an episode record (`candle_index`, `timestamp`, `shadow_source_htf`, `active_range_htf`,
`shadow_cross_range=bucket`, `shadow_formed_idx=state.pending_displacement_formed_idx`,
`direction`, `outcome="PENDING"`) and set it as `_ProbeState.open_episode` (single-slot
correlator). If `open_episode` is already non-`None` when a new restore succeeds, log/record
`"UNRESOLVED_PRIOR_EPISODE_OVERWRITTEN"` loudly instead of silently overwriting — this actively
falsifies the single-episode assumption if it's ever wrong, rather than just asserting it.

**Patch 2 — `ExecutionEngine.build_trade`** (Bucket B: outcome classification). Call the original
unmodified; classify the return value:

```
if trade is None and open_episode is not None:
    # independently recompute which of the 4 None-causes applies, using the verified
    # branch order above, purely from `state` fields (mirrors crt_engine_v2.py:2342-2390)
    outcome = "INVERTED_STOP_REJECTED" if <recomputed guard trips> else "BUILD_TRADE_NONE_OTHER"
elif trade is not None:
    outcome = "TRADE_OPENED"
```

If `open_episode` is set, finalize it with this `outcome`, append to `episodes_resolved`, clear
the slot. Return `trade` unchanged in all cases (pure observer).

**Patch 3 — `StateMachine.reset_to_range`** (episode death before execution). If
`open_episode is not None` when a reset fires, finalize it as `"RESET_BEFORE_EXECUTION"` (covers
off-session filter, zone/parent-bias rejects, soft-conf timeout, `SHADOW_LEAK`, `SWEEP_EXPIRED`,
etc. — any gate that kills the episode before `build_trade` is reached), record the reset
`reason`, clear the slot. Call the original unmodified, return its result.

**Cross-check (optional, secondary signal only)**: also attach a `logging.Handler` on the
`build_trade`-owning logger filtering substring `"inverted SL"` (present in both the LONG and
SHORT warning strings at `:2381`/`:2387`), correlated via a `process_candle` wrapper stashing
"candle currently being processed." Record agreement/disagreement with Patch 2's classification
in `log_handler_disagreement_count` — a disagreement would mean the message text or branch
structure drifted since this plan was written, and should be investigated before trusting the
artifact, but does not block the primary (Patch 2) signal.

Any episode still `open_episode` at end-of-corpus → bucket `"UNRESOLVED_AT_EOF"`.

### Output: `results/analysis/shadow_cross_range_restoration.LATEST.json` (+ `.LATEST.md`)

Contains: `instrument`, `csv_path`/`csv_sha256`, `config_version`, git provenance
(`git_sha`/`tree_dirty`), a contingency table `{SAME_RANGE, CROSS_RANGE, UNKNOWN} ×
{TRADE_OPENED, INVERTED_STOP_REJECTED, RESET_BEFORE_EXECUTION, BUILD_TRADE_NONE_OTHER,
UNRESOLVED_AT_EOF}`, the full per-episode `episodes` list, `log_handler_disagreement_count`, a
`known_n2_sanity_check` block (see Verification), a `self_consistency_check` block, and a
mandatory disclaimer block:

```json
"authority_disclaimer": {
  "economic_claims_allowed": false,
  "n_too_small_for_inference": true,
  "note": "Reports observed counts only. Makes no claim that cross-range restoration causes or
           correlates with inverted-stop outcomes. Not a finding — no G001, no promotion."
}
```

### SITS registration

Add one curated overlay entry to `scripts/governance/seed_script_registry.py` (same shape as the
`rr_confidence_probe`/`soft_conf_ema_double_update_probe` entries): `category="DIAGNOSTIC"`,
`ttl_days=90`, `purpose` = one-sentence description of the probe, `task_refs=["SITS"]` (grep the
registry for the current highest `F-0xx` at implementation time — do not hardcode a finding id
from this plan, since none is registered yet for this investigation and other work may land
first). Then run `script_census.py --write-stubs` → `seed_script_registry.py` →
`generate_script_matrix.py` per `docs/reference/conventions.md` §2.1.

### Verification

1. **Self-consistency**: a standalone `tests/test_shadow_cross_range_probe.py` unit-tests the
   bucketing function in isolation (both-empty / one-empty / equal / unequal inputs → expected
   bucket), independent of the engine. The artifact's own `self_consistency_check` re-derives each
   episode's bucket from its stored fields and asserts it matches what was captured live.
2. **Known n=2 replay (hard assertion, not just informational)**: after a full run, filter
   `episodes` for `shadow_cross_range=="CROSS_RANGE"` and assert the result is *exactly* the two
   already-known episodes — `(candle_index=65, shadow_formed_idx=62, shadow_source_htf=
   "XAUUSD-HTF-000015", active_range_htf="XAUUSD-HTF-000016", direction=SHORT)` and
   `(candle_index=384, shadow_formed_idx=381, shadow_source_htf="XAUUSD-HTF-000095",
   active_range_htf="XAUUSD-HTF-000096", direction=LONG)`. If this doesn't reproduce exactly, the
   probe is instrumenting the wrong moment relative to state mutation and must be fixed before the
   artifact is trusted — script `main()` should exit non-zero on mismatch, not just log it.
3. **Manual run**: `python scripts/analysis/shadow_cross_range_restoration_probe.py` over the
   full XAUUSD M15 corpus (matching the "XAUUSD-only" project convention); confirm zero `src/`
   files changed (`git status --porcelain src/` empty) after the run.

### Open items for the implementation turn (not this plan)

- Re-grep `scripts/governance/seed_script_registry.py` for the current highest `F-0xx` /
  appropriate `task_refs` immediately before writing the overlay entry.
- Re-confirm the exact class holding the logger used inside `ExecutionEngine` (for the optional
  Patch-2b log-handler cross-check) and that the `"inverted SL"` substring hasn't drifted.
- Decide flat vs `{"XAUUSD": {...}}` nesting for the output JSON to match whatever convention
  `results/analysis/` already uses elsewhere (precedent script keeps it flat).

### Critical files

- New: `scripts/analysis/shadow_cross_range_restoration_probe.py`
- New: `tests/test_shadow_cross_range_probe.py`
- Edit (registry only, not source): `scripts/governance/seed_script_registry.py`
- Reference/pattern source (read, not modified): `scripts/analysis/soft_conf_ema_double_update_probe.py`
- Reference (read, not modified): `src/config_layer/crt_engine_v2.py` (`StateMachine.try_shadow_pending_to_expansion:1070-1094`, `StateMachine.reset_to_range:1836-1915`, `ExecutionEngine.build_trade:2339-2444`)
