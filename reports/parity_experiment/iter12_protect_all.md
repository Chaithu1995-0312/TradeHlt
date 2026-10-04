# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T12:13:34.685044
>
> **Authority:** research / documentation only. `crt_state.enabled` stays false.
> Milestone: **transition parity** (not dwell tuning).

## Purpose

Feature completeness is closed. Remaining divergence is **lifecycle** and
**detector semantics**. This report localizes *where* the resolver first
disagrees with the engine on a per-bar basis, so HTF-reset and detector
work can target concrete mismatch cells instead of aggregate dwell totals.

## Inputs

| Input | Path |
|-------|------|
| OHLCV | `data\mt5\XAUUSD_M15.csv` |
| Engine events | `results\run_20260805_105350_XAUUSD\XAUUSD_events.jsonl` |
| Resolver config | `reports\parity_experiment\iter12_protect_all.yaml` |
| Engine mode | `enter` (enter = prev_state / state_distribution basis) |

## Engine timeline reconstruction

- Bars: **47,275**
- STATE_TRANSITION events: **3,869**
- RESET events: **10,869** (HTF=10,666, gap=121, other=82)
- Reset-from histogram: `{'RANGE': 7441, 'SWEEP': 3062, 'DISPLACEMENT': 298, 'SHADOW_PENDING': 8, 'EXPANSION': 43, 'RETEST': 12, 'RESOLUTION': 1, 'EXECUTION': 4}`

### Engine transition pairs (top)

| From | To | N |
|------|----|---|
| RANGE | SWEEP | 3,377 |
| SWEEP | DISPLACEMENT | 315 |
| RANGE | SHADOW_PENDING | 51 |
| SHADOW_PENDING | SWEEP | 43 |
| SWEEP | EXPANSION | 43 |
| EXPANSION | RETEST | 17 |
| DISPLACEMENT | EXPANSION | 17 |
| RETEST | EXECUTION | 5 |
| EXECUTION | RESOLUTION | 1 |

### Reconstruction notes

- Skipped 163 RESET event(s) whose state_from disagreed with the reconstructed state (engine state_from is authoritative; these resets applied to a state the engine was not in at that bar). This is what reconciles reconstructed EXPANSION dwell with state_distribution.
- RESOLUTION appeared in events but not in exit timeline (check ordering).

### Dwell: reconstructed enter-state vs summary reference

| State | Reconstructed (enter) | Summary reference | Δ |
|-------|----------------------|-------------------|---|
| RANGE | 35,170 | 35,159 | +11 |
| SWEEP | 7,055 | 6,987 | +68 |
| DISPLACEMENT | 373 | 373 | +0 |
| EXPANSION | 4,604 | 4,605 | -1 |
| RETEST | 17 | 17 | +0 |
| EXECUTION | 5 | 5 | +0 |
| SHADOW_PENDING | 51 | 51 | +0 |

> **Note (root-caused 2026-07-25):** the events stream is COMPLETE and consistent
> (STATE_TRANSITION count == sum of non-RANGE entry counts; RESET count == RANGE entries).
> The earlier EXPANSION under-count (reconstructed 3,060 vs `state_distribution` 4,605) was
> a RECONSTRUCTION bug, not lossy telemetry: the replay applied RESET events without honoring
> the engine's authoritative `state_from` (reset_to_range emits state_from=current_state,
> crt_engine_v2.py:1712). A reset issued from RANGE/SWEEP was truncating a still-active
> reconstructed EXPANSION. The state_from guard above reconciles the timeline with
> `state_distribution` (EXPANSION 4,604 ≈ 4,605). `expansion_dwell_stats` (≈6,105) is a
> separate metric — the candidate-lifetime INDEX SPAN, not continuous per-bar occupancy.

## Resolver run

- Raw OHLCV bars: **47,275**
- Resolved bars (post-warmup): **47,197** (dropped 78)
- Aligned bars (resolver ∩ engine): **47,197**
- Resolver lifecycle resets: HTF=**4,547** gap=**121** forced=**0**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 18,757 | 35,103 | 35,159 |
| SWEEP | 15,183 | 7,046 | 6,987 |
| DISPLACEMENT | 2,400 | 371 | 373 |
| EXPANSION | 10,082 | 4,604 | 4,605 |
| RETEST | 775 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 0 | 51 | 51 |

## Agreement

- **Exact bar match:** 17,775 / 47,197 (**37.66%**)
- **Mismatch bars:** 29,422 (62.34%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **14164** | 11301 | 1812 | 7239 | 587 | 0 | 0 | 35,103 |
| **SWEEP** | 2649 | **2394** | 343 | 1560 | 100 | 0 | 0 | 7,046 |
| **DISPLACEMENT** | 147 | 119 | **24** | 74 | 7 | 0 | 0 | 371 |
| **EXPANSION** | 1774 | 1339 | 218 | **1193** | 80 | 0 | 0 | 4,604 |
| **RETEST** | 3 | 8 | 2 | 4 | **0** | 0 | 0 | 17 |
| **EXECUTION** | 0 | 4 | 0 | 1 | 0 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 20 | 18 | 1 | 11 | 1 | 0 | **0** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| RANGE | SWEEP | 11,301 | 38.41% |
| RANGE | EXPANSION | 7,239 | 24.60% |
| SWEEP | RANGE | 2,649 | 9.00% |
| RANGE | DISPLACEMENT | 1,812 | 6.16% |
| EXPANSION | RANGE | 1,774 | 6.03% |
| SWEEP | EXPANSION | 1,560 | 5.30% |
| EXPANSION | SWEEP | 1,339 | 4.55% |
| RANGE | RETEST | 587 | 2.00% |
| SWEEP | DISPLACEMENT | 343 | 1.17% |
| EXPANSION | DISPLACEMENT | 218 | 0.74% |
| DISPLACEMENT | RANGE | 147 | 0.50% |
| DISPLACEMENT | SWEEP | 119 | 0.40% |
| SWEEP | RETEST | 100 | 0.34% |
| EXPANSION | RETEST | 80 | 0.27% |
| DISPLACEMENT | EXPANSION | 74 | 0.25% |
| SHADOW_PENDING | RANGE | 20 | 0.07% |
| SHADOW_PENDING | SWEEP | 18 | 0.06% |
| SHADOW_PENDING | EXPANSION | 11 | 0.04% |
| RETEST | SWEEP | 8 | 0.03% |
| DISPLACEMENT | RETEST | 7 | 0.02% |
| EXECUTION | SWEEP | 4 | 0.01% |
| RETEST | EXPANSION | 4 | 0.01% |
| RETEST | RANGE | 3 | 0.01% |
| RETEST | DISPLACEMENT | 2 | 0.01% |
| SHADOW_PENDING | RETEST | 1 | 0.00% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 79 | 81 | 3 | SWEEP | RANGE | 3 |
| 88 | 89 | 2 | SWEEP | RANGE | 2 |
| 92 | 94 | 3 | RANGE | SWEEP | 3 |
| 98 | 98 | 1 | RANGE | SWEEP | 1 |
| 102 | 109 | 8 | RANGE | DISPLACEMENT | 3 |
| 123 | 125 | 3 | DISPLACEMENT | RANGE | 2 |
| 129 | 129 | 1 | SHADOW_PENDING | RANGE | 1 |
| 143 | 145 | 3 | SWEEP | RANGE | 3 |
| 148 | 149 | 2 | SWEEP | RANGE | 2 |
| 152 | 152 | 1 | RANGE | SWEEP | 1 |
| 154 | 155 | 2 | RANGE | SWEEP | 2 |
| 158 | 160 | 3 | RANGE | SWEEP | 3 |
| 162 | 168 | 7 | RANGE | SWEEP | 7 |
| 170 | 170 | 1 | RANGE | SWEEP | 1 |
| 173 | 173 | 1 | SWEEP | RANGE | 1 |
| 176 | 177 | 2 | SWEEP | RANGE | 2 |
| 180 | 205 | 26 | RANGE | SWEEP | 16 |
| 208 | 209 | 2 | SWEEP | RANGE | 2 |
| 220 | 220 | 1 | SWEEP | RANGE | 1 |
| 222 | 222 | 1 | RANGE | SWEEP | 1 |
| 226 | 228 | 3 | RANGE | DISPLACEMENT | 3 |
| 239 | 244 | 6 | SWEEP | RANGE | 3 |
| 246 | 262 | 17 | RANGE | SWEEP | 17 |
| 267 | 268 | 2 | SWEEP | RANGE | 2 |
| 270 | 275 | 6 | RANGE | SWEEP | 6 |
| 281 | 284 | 4 | RANGE | SWEEP | 4 |
| 286 | 308 | 23 | RANGE | SWEEP | 9 |
| 312 | 316 | 5 | RANGE | SWEEP | 4 |
| 318 | 320 | 3 | RANGE | DISPLACEMENT | 1 |
| 330 | 337 | 8 | RANGE | SWEEP | 3 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **2,687**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| RANGE | SWEEP | RANGE | 1,308 |
| RANGE | SWEEP | EXPANSION | 729 |
| RANGE | SWEEP | DISPLACEMENT | 168 |
| SWEEP | DISPLACEMENT | RANGE | 125 |
| SWEEP | DISPLACEMENT | SWEEP | 104 |
| SWEEP | DISPLACEMENT | EXPANSION | 61 |
| RANGE | SWEEP | RETEST | 37 |
| RANGE | SHADOW_PENDING | SWEEP | 19 |
| RANGE | SHADOW_PENDING | RANGE | 18 |
| SWEEP | EXPANSION | SWEEP | 17 |
| SHADOW_PENDING | SWEEP | RANGE | 16 |
| SWEEP | EXPANSION | RANGE | 16 |
| RANGE | SHADOW_PENDING | EXPANSION | 12 |
| DISPLACEMENT | EXPANSION | SWEEP | 10 |
| SHADOW_PENDING | SWEEP | EXPANSION | 8 |
| EXPANSION | RETEST | SWEEP | 7 |
| DISPLACEMENT | EXPANSION | RANGE | 6 |
| EXPANSION | RETEST | RANGE | 4 |
| RETEST | EXECUTION | SWEEP | 4 |
| SWEEP | DISPLACEMENT | RETEST | 4 |
| EXPANSION | RETEST | DISPLACEMENT | 3 |
| EXPANSION | RETEST | EXPANSION | 3 |
| RANGE | SHADOW_PENDING | DISPLACEMENT | 2 |
| EXECUTION | RESOLUTION | SWEEP | 1 |
| SHADOW_PENDING | SWEEP | RETEST | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 78 | 2024-05-23T16:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2360.56000 idx=78 |
| 87 | 2024-05-23T18:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.43000 idx=87 |
| 106 | 2024-05-23T23:00:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2330.87000 idx=106 |
| 122 | 2024-05-24T04:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2326.82000 idx=122 |
| 123 | 2024-05-24T04:15:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.858 wick=5.36000 |
| 128 | 2024-05-24T05:30:00 | RANGE→SHADOW_PENDING | RANGE | Shadow resume: confirming sweep @ 2325.43000 dir=LONG |
| 142 | 2024-05-24T09:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2339.53000 idx=142 |
| 147 | 2024-05-24T10:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.65000 idx=147 |
| 175 | 2024-05-24T17:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2335.56000 idx=175 |
| 195 | 2024-05-24T22:15:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2331.99000 idx=195 |
| 203 | 2024-05-27T01:15:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2337.54000 idx=203 |
| 207 | 2024-05-27T02:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.75000 idx=207 |
| 219 | 2024-05-27T05:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2341.19000 idx=219 |
| 238 | 2024-05-27T10:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2339.56000 idx=238 |
| 266 | 2024-05-27T17:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2357.12000 idx=266 |
| 300 | 2024-05-28T05:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2355.96000 idx=300 |
| 318 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | DISPLACEMENT | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 319 | 2024-05-28T09:45:00 | SHADOW_PENDING→SWEEP | RANGE | Shadow: prior-window displacement restored from idx=316 |
| 319 | 2024-05-28T09:45:00 | SWEEP→EXPANSION | RANGE | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 334 | 2024-05-28T13:30:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2345.84000 idx=334 |
| 342 | 2024-05-28T15:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2357.12000 idx=342 |
| 344 | 2024-05-28T16:00:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.735 wick=4.61000 |
| 391 | 2024-05-29T04:45:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2355.92000 idx=391 |
| 396 | 2024-05-29T06:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2355.68000 idx=396 |
| 408 | 2024-05-29T09:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.939 wick=3.28000 |
| 464 | 2024-05-29T23:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2336.08000 idx=464 |
| 479 | 2024-05-30T03:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2335.25000 idx=479 |
| 483 | 2024-05-30T04:45:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2332.89000 idx=483 |
| 571 | 2024-05-31T03:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2347.60000 idx=571 |
| 576 | 2024-05-31T05:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2347.77000 idx=576 |
| 579 | 2024-05-31T05:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2342.36000 idx=579 |
| 580 | 2024-05-31T06:00:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.864 wick=4.57000 |
| 596 | 2024-05-31T10:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2345.88000 idx=596 |
| 600 | 2024-05-31T11:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2339.73000 idx=600 |
| 710 | 2024-06-03T15:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2334.03000 idx=710 |
| 714 | 2024-06-03T16:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2336.76000 idx=714 |
| 716 | 2024-06-03T17:00:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.651 wick=9.10000 |
| 719 | 2024-06-03T17:45:00 | RANGE→SHADOW_PENDING | RANGE | Shadow resume: confirming sweep @ 2345.34000 dir=SHORT |
| 720 | 2024-06-03T18:00:00 | SHADOW_PENDING→SWEEP | RANGE | Shadow: prior-window displacement restored from idx=716 |
| 720 | 2024-06-03T18:00:00 | SWEEP→EXPANSION | RANGE | Shadow resume: displacement carried from prior HTF window — strength check skipped |

## Interpretation guide (for next milestones)

| Pattern | Likely cause | Next lever |
|---------|--------------|------------|
| Engine RANGE, resolver SWEEP/EXPANSION | Sticky lifecycle / no HTF terminate | HTF reset memory |
| Engine SWEEP, resolver RANGE | Missed sweep detection or funnel order | Sweep detector / funnel |
| Engine DISPLACEMENT, resolver SWEEP/RANGE | Detector threshold / body gate | Engine-grade displacement |
| Engine EXPANSION, resolver RETEST | Permissive retest_flag | Engine-grade retest |
| Engine RETEST, resolver EXPANSION | Retest under-fire | Retest detector |
| Engine RESET edges invisible to resolver | HTF/gap lifecycle | Wire RESET→RANGE in resolver |

## Production stance

- `market_reality.crt_state.enabled = false` — **unchanged**
- CRT engine remains execution authority
- This matrix is the gate for HTF-reset and detector PRs: each change should
  **shrink a named off-diagonal cell** without collapsing SWEEP agreement

