# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T14:38:52.991360
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
| Resolver config | `configs\formulas\market_crt_states.yaml` |
| Engine mode | `exit` (enter = prev_state / state_distribution basis) |

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

- RESOLUTION appeared in events but not in exit timeline (check ordering).

### Dwell: reconstructed enter-state vs summary reference

| State | Reconstructed (enter) | Summary reference | Δ |
|-------|----------------------|-------------------|---|
| RANGE | 35,208 | 35,159 | +49 |
| SWEEP | 6,996 | 6,987 | +9 |
| DISPLACEMENT | 373 | 373 | +0 |
| EXPANSION | 4,625 | 4,605 | +20 |
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
- Resolver lifecycle resets: HTF=**11,232** gap=**93** forced=**82**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 36,918 | 35,130 | 35,159 |
| SWEEP | 7,407 | 6,996 | 6,987 |
| DISPLACEMENT | 389 | 373 | 373 |
| EXPANSION | 2,365 | 4,625 | 4,605 |
| RETEST | 114 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 4 | 51 | 51 |

## Agreement

- **Exact bar match:** 42,400 / 47,197 (**89.84%**)
- **Mismatch bars:** 4,797 (10.16%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **34110** | 0 | 0 | 961 | 59 | 0 | 0 | 35,130 |
| **SWEEP** | 9 | **6773** | 0 | 204 | 10 | 0 | 0 | 6,996 |
| **DISPLACEMENT** | 0 | 0 | **351** | 22 | 0 | 0 | 0 | 373 |
| **EXPANSION** | 2789 | 591 | 38 | **1162** | 45 | 0 | 0 | 4,625 |
| **RETEST** | 8 | 1 | 0 | 8 | **0** | 0 | 0 | 17 |
| **EXECUTION** | 2 | 0 | 0 | 3 | 0 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 0 | 42 | 0 | 5 | 0 | 0 | **4** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| EXPANSION | RANGE | 2,789 | 58.14% |
| RANGE | EXPANSION | 961 | 20.03% |
| EXPANSION | SWEEP | 591 | 12.32% |
| SWEEP | EXPANSION | 204 | 4.25% |
| RANGE | RETEST | 59 | 1.23% |
| EXPANSION | RETEST | 45 | 0.94% |
| SHADOW_PENDING | SWEEP | 42 | 0.88% |
| EXPANSION | DISPLACEMENT | 38 | 0.79% |
| DISPLACEMENT | EXPANSION | 22 | 0.46% |
| SWEEP | RETEST | 10 | 0.21% |
| SWEEP | RANGE | 9 | 0.19% |
| RETEST | RANGE | 8 | 0.17% |
| RETEST | EXPANSION | 8 | 0.17% |
| SHADOW_PENDING | EXPANSION | 5 | 0.10% |
| EXECUTION | EXPANSION | 3 | 0.06% |
| EXECUTION | RANGE | 2 | 0.04% |
| RETEST | SWEEP | 1 | 0.02% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 202 | 202 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 392 | 392 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 485 | 512 | 28 | RANGE | EXPANSION | 20 |
| 793 | 1140 | 348 | EXPANSION | RANGE | 283 |
| 1681 | 1702 | 22 | EXPANSION | RANGE | 18 |
| 1802 | 1802 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 2704 | 2704 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 3118 | 3130 | 13 | EXPANSION | RANGE | 11 |
| 3534 | 3573 | 40 | RANGE | EXPANSION | 32 |
| 4541 | 4544 | 4 | RANGE | RETEST | 2 |
| 4786 | 4845 | 60 | EXPANSION | RANGE | 55 |
| 5086 | 5089 | 4 | RANGE | EXPANSION | 2 |
| 5092 | 5305 | 214 | EXPANSION | RANGE | 167 |
| 7830 | 7858 | 29 | RANGE | EXPANSION | 23 |
| 7860 | 7861 | 2 | SWEEP | RANGE | 2 |
| 8181 | 8250 | 70 | RANGE | EXPANSION | 51 |
| 8568 | 8568 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 8573 | 8632 | 60 | RANGE | EXPANSION | 41 |
| 9196 | 9196 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 9198 | 9198 | 1 | RETEST | EXPANSION | 1 |
| 9313 | 9313 | 1 | RETEST | EXPANSION | 1 |
| 9496 | 9496 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 10274 | 10276 | 3 | DISPLACEMENT | EXPANSION | 1 |
| 10300 | 10355 | 56 | EXPANSION | RANGE | 45 |
| 11932 | 11932 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 11934 | 11934 | 1 | RETEST | EXPANSION | 1 |
| 11985 | 12195 | 211 | EXPANSION | RANGE | 171 |
| 12741 | 12807 | 67 | RANGE | EXPANSION | 59 |
| 13289 | 13292 | 4 | SHADOW_PENDING | SWEEP | 1 |
| 13762 | 13763 | 2 | EXPANSION | DISPLACEMENT | 1 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **227**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| RANGE | SWEEP | EXPANSION | 85 |
| RANGE | SHADOW_PENDING | SWEEP | 42 |
| SHADOW_PENDING | SWEEP | EXPANSION | 34 |
| SWEEP | DISPLACEMENT | EXPANSION | 11 |
| EXPANSION | RETEST | RANGE | 8 |
| DISPLACEMENT | EXPANSION | DISPLACEMENT | 8 |
| EXPANSION | RETEST | EXPANSION | 8 |
| SWEEP | EXPANSION | SWEEP | 7 |
| RANGE | SHADOW_PENDING | EXPANSION | 5 |
| RANGE | SWEEP | RETEST | 4 |
| RANGE | SWEEP | RANGE | 4 |
| RETEST | EXECUTION | EXPANSION | 3 |
| RETEST | EXECUTION | RANGE | 2 |
| SHADOW_PENDING | SWEEP | RANGE | 2 |
| SWEEP | EXPANSION | RANGE | 2 |
| EXPANSION | RETEST | SWEEP | 1 |
| EXECUTION | RESOLUTION | RANGE | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 202 | 2024-05-24T05:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2325.43000 dir=LONG |
| 392 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 393 | 2024-05-28T09:45:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=316 |
| 490 | 2024-05-29T11:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2348.86000 idx=416 |
| 505 | 2024-05-29T14:45:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2338.63000 idx=431 |
| 510 | 2024-05-29T16:00:00 | RANGE→SWEEP | RETEST | Sweep @ 2335.96000 idx=436 |
| 793 | 2024-06-03T17:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2345.34000 dir=SHORT |
| 794 | 2024-06-03T18:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 1140 | 2024-06-07T12:30:00 | EXPANSION→RETEST | SWEEP | Retest | depth_abs=1.90000 ceiling=2.54100 |
| 1681 | 2024-06-17T09:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2316.56000 dir=LONG |
| 1682 | 2024-06-17T10:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 1701 | 2024-06-17T14:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=1.36000 ceiling=1.40850 |
| 1702 | 2024-06-17T15:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 1703 | 2024-06-17T15:15:00 | EXECUTION→RESOLUTION | RANGE | Trade closed: TP1 |
| 1802 | 2024-06-18T17:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2327.11000 dir=SHORT |
| 2704 | 2024-07-02T15:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2319.07000 dir=LONG |
| 2705 | 2024-07-02T15:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=2628 |
| 3118 | 2024-07-09T06:00:00 | SHADOW_PENDING→SWEEP | RANGE | Shadow: prior-window displacement restored from idx=3040 |
| 3118 | 2024-07-09T06:00:00 | SWEEP→EXPANSION | RANGE | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 3129 | 2024-07-09T08:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=0.75000 ceiling=0.82800 |
| 3130 | 2024-07-09T09:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 3540 | 2024-07-15T19:30:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2439.78000 idx=3466 |
| 3569 | 2024-07-16T03:45:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2420.02000 idx=3495 |
| 3570 | 2024-07-16T04:00:00 | SWEEP→DISPLACEMENT | EXPANSION | Displacement | body_ratio=0.856 wick=4.11000 |
| 3572 | 2024-07-16T04:30:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2427.05000 idx=3498 |
| 3573 | 2024-07-16T04:45:00 | SWEEP→DISPLACEMENT | EXPANSION | Displacement | body_ratio=0.746 wick=2.80000 |
| 4786 | 2024-08-02T09:00:00 | DISPLACEMENT→EXPANSION | DISPLACEMENT | Bearish expansion | close=2465.17000 disp_close=2466.74000 |
| 5089 | 2024-08-07T15:45:00 | RANGE→SHADOW_PENDING | EXPANSION | Shadow resume: confirming sweep @ 2407.06000 dir=SHORT |
| 5090 | 2024-08-07T16:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=5011 |
| 7845 | 2024-09-18T17:15:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2568.10000 idx=7771 |
| 7860 | 2024-09-18T21:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2567.09000 idx=7786 |
| 8186 | 2024-09-24T10:30:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2622.68000 idx=8112 |
| 8208 | 2024-09-24T16:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2636.67000 idx=8134 |
| 8212 | 2024-09-24T17:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2639.20000 idx=8138 |
| 8217 | 2024-09-24T18:15:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2648.45000 idx=8143 |
| 8221 | 2024-09-24T19:15:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2650.56000 idx=8147 |
| 8222 | 2024-09-24T19:30:00 | SWEEP→DISPLACEMENT | EXPANSION | Displacement | body_ratio=0.781 wick=8.73000 |
| 8228 | 2024-09-24T21:00:00 | RANGE→SWEEP | EXPANSION | Sweep @ 2655.40000 idx=8154 |
| 8568 | 2024-09-30T14:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2634.50000 dir=LONG |
| 8569 | 2024-09-30T14:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=8492 |

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

