# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T12:09:29.962581
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
| Resolver config | `reports\parity_experiment\iter7_max_loose.yaml` |
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
- Resolver lifecycle resets: HTF=**11,397** gap=**121** forced=**0**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 38,478 | 35,103 | 35,159 |
| SWEEP | 5,048 | 7,046 | 6,987 |
| DISPLACEMENT | 1,097 | 371 | 373 |
| EXPANSION | 1,211 | 4,604 | 4,605 |
| RETEST | 237 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 1,126 | 51 | 51 |

## Agreement

- **Exact bar match:** 29,361 / 47,197 (**62.21%**)
- **Mismatch bars:** 17,836 (37.79%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **28556** | 3785 | 911 | 931 | 172 | 0 | 748 | 35,103 |
| **SWEEP** | 5699 | **744** | 80 | 216 | 49 | 0 | 258 | 7,046 |
| **DISPLACEMENT** | 300 | 46 | **4** | 7 | 1 | 0 | 13 | 371 |
| **EXPANSION** | 3858 | 469 | 101 | **56** | 15 | 0 | 105 | 4,604 |
| **RETEST** | 14 | 2 | 0 | 0 | **0** | 0 | 1 | 17 |
| **EXECUTION** | 3 | 1 | 1 | 0 | 0 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 48 | 1 | 0 | 1 | 0 | 0 | **1** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| SWEEP | RANGE | 5,699 | 31.95% |
| EXPANSION | RANGE | 3,858 | 21.63% |
| RANGE | SWEEP | 3,785 | 21.22% |
| RANGE | EXPANSION | 931 | 5.22% |
| RANGE | DISPLACEMENT | 911 | 5.11% |
| RANGE | SHADOW_PENDING | 748 | 4.19% |
| EXPANSION | SWEEP | 469 | 2.63% |
| DISPLACEMENT | RANGE | 300 | 1.68% |
| SWEEP | SHADOW_PENDING | 258 | 1.45% |
| SWEEP | EXPANSION | 216 | 1.21% |
| RANGE | RETEST | 172 | 0.96% |
| EXPANSION | SHADOW_PENDING | 105 | 0.59% |
| EXPANSION | DISPLACEMENT | 101 | 0.57% |
| SWEEP | DISPLACEMENT | 80 | 0.45% |
| SWEEP | RETEST | 49 | 0.27% |
| SHADOW_PENDING | RANGE | 48 | 0.27% |
| DISPLACEMENT | SWEEP | 46 | 0.26% |
| EXPANSION | RETEST | 15 | 0.08% |
| RETEST | RANGE | 14 | 0.08% |
| DISPLACEMENT | SHADOW_PENDING | 13 | 0.07% |
| DISPLACEMENT | EXPANSION | 7 | 0.04% |
| EXECUTION | RANGE | 3 | 0.02% |
| RETEST | SWEEP | 2 | 0.01% |
| RETEST | SHADOW_PENDING | 1 | 0.01% |
| EXECUTION | DISPLACEMENT | 1 | 0.01% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 79 | 81 | 3 | SWEEP | RANGE | 3 |
| 88 | 89 | 2 | SWEEP | RANGE | 2 |
| 92 | 97 | 6 | RANGE | SWEEP | 3 |
| 99 | 101 | 3 | SWEEP | RANGE | 3 |
| 107 | 109 | 3 | SWEEP | RANGE | 3 |
| 123 | 125 | 3 | DISPLACEMENT | RANGE | 2 |
| 129 | 129 | 1 | SHADOW_PENDING | RANGE | 1 |
| 143 | 145 | 3 | SWEEP | RANGE | 3 |
| 148 | 149 | 2 | SWEEP | RANGE | 2 |
| 152 | 152 | 1 | RANGE | SWEEP | 1 |
| 154 | 154 | 1 | RANGE | SWEEP | 1 |
| 156 | 157 | 2 | SWEEP | RANGE | 2 |
| 161 | 161 | 1 | SWEEP | RANGE | 1 |
| 168 | 173 | 6 | SWEEP | RANGE | 2 |
| 176 | 177 | 2 | SWEEP | RANGE | 2 |
| 180 | 182 | 3 | RANGE | SWEEP | 2 |
| 184 | 186 | 3 | RANGE | SHADOW_PENDING | 3 |
| 192 | 194 | 3 | RANGE | DISPLACEMENT | 2 |
| 196 | 198 | 3 | SWEEP | SHADOW_PENDING | 2 |
| 200 | 202 | 3 | RANGE | DISPLACEMENT | 2 |
| 204 | 205 | 2 | SWEEP | SHADOW_PENDING | 1 |
| 208 | 209 | 2 | SWEEP | RANGE | 2 |
| 220 | 220 | 1 | SWEEP | RANGE | 1 |
| 222 | 225 | 4 | SWEEP | RANGE | 3 |
| 239 | 242 | 4 | SWEEP | RANGE | 3 |
| 244 | 246 | 3 | RANGE | SWEEP | 1 |
| 248 | 250 | 3 | RANGE | SWEEP | 2 |
| 267 | 268 | 2 | SWEEP | RANGE | 2 |
| 270 | 270 | 1 | RANGE | SWEEP | 1 |
| 281 | 282 | 2 | RANGE | SWEEP | 2 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **3,497**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| RANGE | SWEEP | RANGE | 2,691 |
| SWEEP | DISPLACEMENT | RANGE | 282 |
| RANGE | SWEEP | DISPLACEMENT | 121 |
| RANGE | SWEEP | EXPANSION | 116 |
| RANGE | SWEEP | SHADOW_PENDING | 59 |
| SHADOW_PENDING | SWEEP | RANGE | 41 |
| SWEEP | EXPANSION | RANGE | 41 |
| RANGE | SHADOW_PENDING | RANGE | 39 |
| RANGE | SWEEP | RETEST | 20 |
| EXPANSION | RETEST | RANGE | 16 |
| DISPLACEMENT | EXPANSION | RANGE | 15 |
| SWEEP | DISPLACEMENT | SWEEP | 13 |
| SWEEP | DISPLACEMENT | SHADOW_PENDING | 11 |
| RANGE | SHADOW_PENDING | SWEEP | 9 |
| SWEEP | DISPLACEMENT | EXPANSION | 7 |
| RETEST | EXECUTION | SWEEP | 2 |
| RETEST | EXECUTION | RANGE | 2 |
| DISPLACEMENT | EXPANSION | SHADOW_PENDING | 2 |
| RANGE | SHADOW_PENDING | DISPLACEMENT | 2 |
| EXPANSION | RETEST | DISPLACEMENT | 1 |
| RETEST | EXECUTION | SHADOW_PENDING | 1 |
| EXECUTION | RESOLUTION | RANGE | 1 |
| SWEEP | DISPLACEMENT | RETEST | 1 |
| SHADOW_PENDING | SWEEP | SHADOW_PENDING | 1 |
| SWEEP | EXPANSION | SHADOW_PENDING | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 78 | 2024-05-23T16:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2360.56000 idx=78 |
| 87 | 2024-05-23T18:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.43000 idx=87 |
| 98 | 2024-05-23T21:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2331.86000 idx=98 |
| 106 | 2024-05-23T23:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2330.87000 idx=106 |
| 122 | 2024-05-24T04:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2326.82000 idx=122 |
| 123 | 2024-05-24T04:15:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.858 wick=5.36000 |
| 128 | 2024-05-24T05:30:00 | RANGE→SHADOW_PENDING | RANGE | Shadow resume: confirming sweep @ 2325.43000 dir=LONG |
| 142 | 2024-05-24T09:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2339.53000 idx=142 |
| 147 | 2024-05-24T10:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.65000 idx=147 |
| 155 | 2024-05-24T12:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2342.41000 idx=155 |
| 160 | 2024-05-24T13:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2343.87000 idx=160 |
| 170 | 2024-05-24T16:00:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2344.16000 idx=170 |
| 175 | 2024-05-24T17:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2335.56000 idx=175 |
| 195 | 2024-05-24T22:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2331.99000 idx=195 |
| 203 | 2024-05-27T01:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2337.54000 idx=203 |
| 207 | 2024-05-27T02:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2340.75000 idx=207 |
| 219 | 2024-05-27T05:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2341.19000 idx=219 |
| 238 | 2024-05-27T10:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2339.56000 idx=238 |
| 266 | 2024-05-27T17:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2357.12000 idx=266 |
| 284 | 2024-05-28T01:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2351.32000 idx=284 |
| 300 | 2024-05-28T05:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2355.96000 idx=300 |
| 315 | 2024-05-28T08:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2349.67000 idx=315 |
| 316 | 2024-05-28T09:00:00 | SWEEP→DISPLACEMENT | SHADOW_PENDING | Displacement | body_ratio=0.909 wick=3.96000 |
| 318 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 319 | 2024-05-28T09:45:00 | SHADOW_PENDING→SWEEP | RANGE | Shadow: prior-window displacement restored from idx=316 |
| 319 | 2024-05-28T09:45:00 | SWEEP→EXPANSION | RANGE | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 334 | 2024-05-28T13:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2345.84000 idx=334 |
| 342 | 2024-05-28T15:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2357.12000 idx=342 |
| 344 | 2024-05-28T16:00:00 | SWEEP→DISPLACEMENT | RANGE | Displacement | body_ratio=0.735 wick=4.61000 |
| 391 | 2024-05-29T04:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2355.92000 idx=391 |
| 396 | 2024-05-29T06:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2355.68000 idx=396 |
| 408 | 2024-05-29T09:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.939 wick=3.28000 |
| 410 | 2024-05-29T09:30:00 | RANGE→SWEEP | DISPLACEMENT | Sweep @ 2351.14000 idx=410 |
| 416 | 2024-05-29T11:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2348.86000 idx=416 |
| 431 | 2024-05-29T14:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2338.63000 idx=431 |
| 436 | 2024-05-29T16:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2335.96000 idx=436 |
| 464 | 2024-05-29T23:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2336.08000 idx=464 |
| 479 | 2024-05-30T03:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2335.25000 idx=479 |
| 483 | 2024-05-30T04:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2332.89000 idx=483 |
| 512 | 2024-05-30T12:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2337.89000 idx=512 |

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

