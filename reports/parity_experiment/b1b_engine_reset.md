# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T13:15:55.004024
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
- Resolver lifecycle resets: HTF=**1,047** gap=**0** forced=**10,840**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 38,462 | 35,130 | 35,159 |
| SWEEP | 7,892 | 6,996 | 6,987 |
| DISPLACEMENT | 335 | 373 | 373 |
| EXPANSION | 447 | 4,625 | 4,605 |
| RETEST | 15 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 46 | 51 | 51 |

## Agreement

- **Exact bar match:** 35,891 / 47,197 (**76.05%**)
- **Mismatch bars:** 11,306 (23.95%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **31703** | 3427 | 0 | 0 | 0 | 0 | 0 | 35,130 |
| **SWEEP** | 3061 | **3687** | 248 | 0 | 0 | 0 | 0 | 6,996 |
| **DISPLACEMENT** | 298 | 17 | **56** | 2 | 0 | 0 | 0 | 373 |
| **EXPANSION** | 3371 | 719 | 30 | **445** | 15 | 0 | 45 | 4,625 |
| **RETEST** | 16 | 0 | 0 | 0 | **0** | 0 | 1 | 17 |
| **EXECUTION** | 5 | 0 | 0 | 0 | 0 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 8 | 42 | 1 | 0 | 0 | 0 | **0** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| RANGE | SWEEP | 3,427 | 30.31% |
| EXPANSION | RANGE | 3,371 | 29.82% |
| SWEEP | RANGE | 3,061 | 27.07% |
| EXPANSION | SWEEP | 719 | 6.36% |
| DISPLACEMENT | RANGE | 298 | 2.64% |
| SWEEP | DISPLACEMENT | 248 | 2.19% |
| EXPANSION | SHADOW_PENDING | 45 | 0.40% |
| SHADOW_PENDING | SWEEP | 42 | 0.37% |
| EXPANSION | DISPLACEMENT | 30 | 0.27% |
| DISPLACEMENT | SWEEP | 17 | 0.15% |
| RETEST | RANGE | 16 | 0.14% |
| EXPANSION | RETEST | 15 | 0.13% |
| SHADOW_PENDING | RANGE | 8 | 0.07% |
| EXECUTION | RANGE | 5 | 0.04% |
| DISPLACEMENT | EXPANSION | 2 | 0.02% |
| SHADOW_PENDING | DISPLACEMENT | 1 | 0.01% |
| RETEST | SHADOW_PENDING | 1 | 0.01% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 96 | 96 | 1 | RANGE | SWEEP | 1 |
| 99 | 99 | 1 | SWEEP | RANGE | 1 |
| 102 | 103 | 2 | RANGE | SWEEP | 1 |
| 124 | 125 | 2 | RANGE | SWEEP | 1 |
| 127 | 127 | 1 | DISPLACEMENT | RANGE | 1 |
| 140 | 140 | 1 | RANGE | SWEEP | 1 |
| 143 | 143 | 1 | SWEEP | RANGE | 1 |
| 146 | 147 | 2 | RANGE | SWEEP | 1 |
| 152 | 152 | 1 | RANGE | SWEEP | 1 |
| 155 | 155 | 1 | SWEEP | RANGE | 1 |
| 161 | 161 | 1 | RANGE | SWEEP | 1 |
| 163 | 163 | 1 | SWEEP | RANGE | 1 |
| 168 | 168 | 1 | RANGE | SWEEP | 1 |
| 171 | 172 | 2 | SWEEP | RANGE | 1 |
| 175 | 175 | 1 | SWEEP | RANGE | 1 |
| 180 | 180 | 1 | RANGE | SWEEP | 1 |
| 183 | 183 | 1 | SWEEP | RANGE | 1 |
| 196 | 197 | 2 | RANGE | SWEEP | 1 |
| 199 | 199 | 1 | DISPLACEMENT | RANGE | 1 |
| 202 | 203 | 2 | RANGE | SWEEP | 1 |
| 216 | 216 | 1 | RANGE | SWEEP | 1 |
| 219 | 219 | 1 | SWEEP | RANGE | 1 |
| 221 | 221 | 1 | RANGE | SWEEP | 1 |
| 223 | 223 | 1 | SWEEP | RANGE | 1 |
| 226 | 227 | 2 | RANGE | SWEEP | 1 |
| 229 | 229 | 1 | RANGE | SWEEP | 1 |
| 231 | 231 | 1 | SWEEP | RANGE | 1 |
| 234 | 235 | 2 | RANGE | SWEEP | 1 |
| 242 | 244 | 3 | RANGE | SWEEP | 2 |
| 247 | 247 | 1 | SWEEP | RANGE | 1 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **202**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| SWEEP | DISPLACEMENT | SWEEP | 67 |
| RANGE | SHADOW_PENDING | SWEEP | 51 |
| SWEEP | EXPANSION | SWEEP | 42 |
| DISPLACEMENT | EXPANSION | DISPLACEMENT | 14 |
| EXPANSION | RETEST | RANGE | 11 |
| EXPANSION | RETEST | SWEEP | 4 |
| RETEST | EXECUTION | RANGE | 4 |
| DISPLACEMENT | EXPANSION | SWEEP | 3 |
| EXECUTION | RESOLUTION | RANGE | 1 |
| EXPANSION | RETEST | SHADOW_PENDING | 1 |
| SHADOW_PENDING | SWEEP | DISPLACEMENT | 1 |
| SWEEP | EXPANSION | DISPLACEMENT | 1 |
| EXPANSION | RETEST | DISPLACEMENT | 1 |
| RETEST | EXECUTION | SHADOW_PENDING | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 202 | 2024-05-24T05:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2325.43000 dir=LONG |
| 392 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 393 | 2024-05-28T09:45:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 482 | 2024-05-29T09:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.939 wick=3.28000 |
| 790 | 2024-06-03T17:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.651 wick=9.10000 |
| 793 | 2024-06-03T17:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2345.34000 dir=SHORT |
| 794 | 2024-06-03T18:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 1140 | 2024-06-07T12:30:00 | EXPANSION→RETEST | SWEEP | Retest | depth_abs=1.90000 ceiling=2.54100 |
| 1594 | 2024-06-14T11:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.660 wick=6.80000 |
| 1681 | 2024-06-17T09:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2316.56000 dir=LONG |
| 1682 | 2024-06-17T10:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 1701 | 2024-06-17T14:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=1.36000 ceiling=1.40850 |
| 1702 | 2024-06-17T15:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 1703 | 2024-06-17T15:15:00 | EXECUTION→RESOLUTION | RANGE | Trade closed: TP1 |
| 1802 | 2024-06-18T17:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2327.11000 dir=SHORT |
| 2704 | 2024-07-02T15:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2319.07000 dir=LONG |
| 2705 | 2024-07-02T15:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 2710 | 2024-07-02T16:30:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.669 wick=6.67000 |
| 2917 | 2024-07-05T01:45:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.930 wick=1.57000 |
| 3117 | 2024-07-09T05:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2366.71000 dir=SHORT |
| 3118 | 2024-07-09T06:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 3129 | 2024-07-09T08:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=0.75000 ceiling=0.82800 |
| 3130 | 2024-07-09T09:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 3406 | 2024-07-12T09:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.890 wick=2.45000 |
| 3577 | 2024-07-16T05:45:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.959 wick=2.96000 |
| 3866 | 2024-07-19T09:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.690 wick=9.47000 |
| 3941 | 2024-07-22T04:45:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.980 wick=3.53000 |
| 4786 | 2024-08-02T09:00:00 | DISPLACEMENT→EXPANSION | DISPLACEMENT | Bearish expansion | close=2465.17000 disp_close=2466.74000 |
| 5089 | 2024-08-07T15:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2407.06000 dir=SHORT |
| 5090 | 2024-08-07T16:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 6054 | 2024-08-22T04:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.676 wick=3.52000 |
| 6334 | 2024-08-27T05:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.651 wick=4.55000 |
| 6458 | 2024-08-28T13:00:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.824 wick=3.64000 |
| 6469 | 2024-08-28T15:45:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.958 wick=3.85000 |
| 7290 | 2024-09-10T16:30:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.691 wick=6.61000 |
| 7754 | 2024-09-17T17:30:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.890 wick=6.83000 |
| 8178 | 2024-09-24T08:30:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.688 wick=6.67000 |
| 8438 | 2024-09-27T04:30:00 | SWEEP→DISPLACEMENT | SWEEP | Displacement | body_ratio=0.674 wick=5.74000 |
| 8568 | 2024-09-30T14:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2634.50000 dir=LONG |
| 8569 | 2024-09-30T14:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |

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

