# Phase-1 SHADOW memory TIMING-RACE note

**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · no Case reopen · no object widening · no freeze work · no TTL flip · no economic promotion

**Index-join (2026-09-10):** engine `candle_index` ≠ CSV/parquet `bar_index` (offset +62). This note’s **lifecycle** counts (0/45 live SWEEP, 33/45 no-sweep, pending_dir, age-at-reset) stay valid — they are engine-domain or use `candle.timestamp` hour, not a CSV-row join. Do **not** mix this session line with the CREATE census parquet-joined session/H20 tables (`run_20260909_202201` `DO_NOT_USE_UNTIL_TIMESTAMP_JOIN`). Restore `parent htf_state` here was joined via `structure_context` on collapse_idx — treat that HTF/parent line as **not** CSV-time context until a timestamp join.

See also `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`. Timing-race session is Clock A (`candle.timestamp`). Do not mix with CREATE census parquet-join session tables (`create_session_hour_tables` INVALIDATED).

**Corpus:** Phase-1 XAUUSD · csv sha256 `4d73f5cebe33ec91…` · config `v2_htfcrt_2026_08`
**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_timing_race.json`
**Mined from:** prior `memory_create_expire.json` + `memory_subsystem.json` + probe `XAUUSD_events.jsonl` (no full BT re-run)

## Locked binary

HTF_CHANGED_WHILE_DISPLACEMENT → pending memory → RANGE → same-dir sweep before TTL=4 → restore → EXPANSION. Dominant gate = memory survival. Compare restore(6) vs expire(45).

## Why 45 expire without matching sweep

- Live-window engine SWEEP events (either dir) among expires: **0 same + 0 opposite** (rows with any live SWEEP: 0/45).
- Leave-RANGE transitions in live window: **0/45**.
- Interpretation (descriptive): for these 45, no confirming same-dir sweep arrived while pending memory was still live; TTL countdown on RANGE exhausted to clear.

## Near-miss classes

- `NO_SWEEP_IN_LIVE_OR_POST_HORIZON`: **33/45**
- `ONLY_OPPOSITE_DIR_AROUND_EXPIRY`: **9/45**
- `SAME_DIR_ON_EXPIRE_BAR_TOO_LATE`: **2/45**
- `SAME_DIR_AFTER_EXPIRY_WITHIN_HORIZON`: **1/45**

Same-dir SWEEP on expire bar (after TTL clear, too late by engine order): **2/45**.
Same-dir SWEEP within +4 bars after expire_idx: **1/45**.
Same-dir after expiry including expire bar: **3/45**.

## Restore vs expire concentrations (descriptive)

- pending_dir: restores `{'SHORT': 2, 'LONG': 4}` vs expires `{'SHORT': 30, 'LONG': 15}`
- age_at_reset: restores `{3: 4, 4: 1, 2: 1}` vs expires `{1: 20, 5: 2, 3: 6, 2: 10, 4: 4, 7: 3}`
- session: restores `{'LONDON_NY_OVERLAP_13_17': 2, 'NY_17_22': 2, 'ASIA_0_8': 1, 'LONDON_8_13': 1}` vs expires `{'LONDON_8_13': 10, 'ASIA_0_8': 11, 'OFFHOURS_22_24': 3, 'NY_17_22': 16, 'LONDON_NY_OVERLAP_13_17': 5}`
- source_htf / HTF class: expires 45 unique window ids; class taxonomy UNAVAILABLE; restores parent htf_state `{'ACCUMULATION': 3, 'DISTRIBUTION': 2, 'EXPANSION': 1}`

## Engine timing note

RANGE branch decrements TTL then clears pending fields when ttl hits 0 **before** `detect_sweep`. A same-dir sweep on the expire bar cannot arm SHADOW_PENDING.

## UNAVAILABLE

- expire_parent_crt / parent_track_state / parent_bias / htf_state: UNAVAILABLE
- HTF class taxonomy beyond source_htf window id: UNAVAILABLE
- detect_sweep true-negatives / failed detect attempts without SWEEP event: UNAVAILABLE
- bar-by-bar OHLC reconstruction of sweep proxies independent of engine: NOT_USED
- create_sample reason strings for memory_id>50: PARTIAL

## Non-claims

- No economic performance claim.
- No recommendation to change TTL.
- No freeze / economic promotion work.
- Session buckets are descriptive broker-local hour bins, not corrected UTC session labels.
