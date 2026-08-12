# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T13:37:56.056286
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
- Resolver lifecycle resets: HTF=**937** gap=**0** forced=**10,840**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 38,062 | 35,130 | 35,159 |
| SWEEP | 7,725 | 6,996 | 6,987 |
| DISPLACEMENT | 403 | 373 | 373 |
| EXPANSION | 886 | 4,625 | 4,605 |
| RETEST | 30 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 91 | 51 | 51 |

## Agreement

- **Exact bar match:** 43,359 / 47,197 (**91.87%**)
- **Mismatch bars:** 3,838 (8.13%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **35130** | 0 | 0 | 0 | 0 | 0 | 0 | 35,130 |
| **SWEEP** | 0 | **6996** | 0 | 0 | 0 | 0 | 0 | 6,996 |
| **DISPLACEMENT** | 0 | 0 | **362** | 11 | 0 | 0 | 0 | 373 |
| **EXPANSION** | 2920 | 675 | 41 | **871** | 30 | 0 | 88 | 4,625 |
| **RETEST** | 8 | 3 | 0 | 3 | **0** | 0 | 3 | 17 |
| **EXECUTION** | 4 | 0 | 0 | 1 | 0 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 0 | 51 | 0 | 0 | 0 | 0 | **0** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| EXPANSION | RANGE | 2,920 | 76.08% |
| EXPANSION | SWEEP | 675 | 17.59% |
| EXPANSION | SHADOW_PENDING | 88 | 2.29% |
| SHADOW_PENDING | SWEEP | 51 | 1.33% |
| EXPANSION | DISPLACEMENT | 41 | 1.07% |
| EXPANSION | RETEST | 30 | 0.78% |
| DISPLACEMENT | EXPANSION | 11 | 0.29% |
| RETEST | RANGE | 8 | 0.21% |
| EXECUTION | RANGE | 4 | 0.10% |
| RETEST | SWEEP | 3 | 0.08% |
| RETEST | EXPANSION | 3 | 0.08% |
| RETEST | SHADOW_PENDING | 3 | 0.08% |
| EXECUTION | EXPANSION | 1 | 0.03% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 202 | 202 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 392 | 393 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 793 | 1140 | 348 | EXPANSION | RANGE | 280 |
| 1681 | 1702 | 22 | EXPANSION | RANGE | 18 |
| 1802 | 1802 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 2704 | 2705 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 3117 | 3130 | 14 | EXPANSION | RANGE | 10 |
| 3534 | 3534 | 1 | DISPLACEMENT | EXPANSION | 1 |
| 4786 | 4845 | 60 | EXPANSION | RANGE | 52 |
| 5086 | 5086 | 1 | DISPLACEMENT | EXPANSION | 1 |
| 5089 | 5305 | 217 | EXPANSION | RANGE | 168 |
| 7830 | 7830 | 1 | DISPLACEMENT | EXPANSION | 1 |
| 8568 | 8574 | 7 | EXPANSION | SWEEP | 2 |
| 9196 | 9198 | 3 | SHADOW_PENDING | SWEEP | 1 |
| 9313 | 9313 | 1 | RETEST | EXPANSION | 1 |
| 9496 | 9497 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 10274 | 10274 | 1 | DISPLACEMENT | EXPANSION | 1 |
| 10276 | 10355 | 80 | EXPANSION | RANGE | 65 |
| 11932 | 11934 | 3 | SHADOW_PENDING | SWEEP | 1 |
| 11985 | 12195 | 211 | EXPANSION | RANGE | 171 |
| 13289 | 13292 | 4 | SHADOW_PENDING | SWEEP | 1 |
| 13762 | 13763 | 2 | EXPANSION | DISPLACEMENT | 1 |
| 13988 | 13989 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 14501 | 14504 | 4 | SHADOW_PENDING | SWEEP | 1 |
| 15144 | 15145 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 16091 | 16109 | 19 | EXPANSION | RANGE | 16 |
| 16154 | 16154 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 16176 | 16569 | 394 | EXPANSION | RANGE | 291 |
| 16776 | 16777 | 2 | SHADOW_PENDING | SWEEP | 1 |
| 16910 | 17029 | 120 | EXPANSION | RANGE | 96 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **126**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| RANGE | SHADOW_PENDING | SWEEP | 51 |
| SWEEP | EXPANSION | SWEEP | 42 |
| EXPANSION | RETEST | RANGE | 8 |
| DISPLACEMENT | EXPANSION | DISPLACEMENT | 8 |
| RETEST | EXECUTION | RANGE | 4 |
| EXPANSION | RETEST | SWEEP | 3 |
| EXPANSION | RETEST | EXPANSION | 3 |
| EXPANSION | RETEST | SHADOW_PENDING | 3 |
| EXECUTION | RESOLUTION | RANGE | 1 |
| SHADOW_PENDING | SWEEP | DISPLACEMENT | 1 |
| SWEEP | EXPANSION | DISPLACEMENT | 1 |
| RETEST | EXECUTION | EXPANSION | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 202 | 2024-05-24T05:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2325.43000 dir=LONG |
| 392 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 393 | 2024-05-28T09:45:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
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
| 2705 | 2024-07-02T15:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 3117 | 2024-07-09T05:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2366.71000 dir=SHORT |
| 3118 | 2024-07-09T06:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 3129 | 2024-07-09T08:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=0.75000 ceiling=0.82800 |
| 3130 | 2024-07-09T09:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 4786 | 2024-08-02T09:00:00 | DISPLACEMENT→EXPANSION | DISPLACEMENT | Bearish expansion | close=2465.17000 disp_close=2466.74000 |
| 5089 | 2024-08-07T15:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2407.06000 dir=SHORT |
| 5090 | 2024-08-07T16:00:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 8568 | 2024-09-30T14:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2634.50000 dir=LONG |
| 8569 | 2024-09-30T14:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 8573 | 2024-09-30T15:15:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=1.94000 ceiling=3.50850 |
| 8574 | 2024-09-30T15:30:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 9196 | 2024-10-09T10:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2609.18000 dir=LONG |
| 9197 | 2024-10-09T10:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 9198 | 2024-10-09T10:30:00 | EXPANSION→RETEST | SWEEP | Retest | depth_abs=1.64000 ceiling=2.04450 |
| 9313 | 2024-10-10T16:15:00 | EXPANSION→RETEST | EXPANSION | Retest | depth_abs=0.74000 ceiling=1.32493 |
| 9496 | 2024-10-14T16:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2648.44000 dir=LONG |
| 9497 | 2024-10-14T16:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 10276 | 2024-10-25T04:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2731.29000 dir=LONG |
| 10277 | 2024-10-25T04:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 11932 | 2024-11-20T04:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2641.70000 dir=SHORT |
| 11933 | 2024-11-20T04:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 11934 | 2024-11-20T04:30:00 | EXPANSION→RETEST | SWEEP | Retest | depth_abs=1.05000 ceiling=1.46100 |
| 11985 | 2024-11-20T17:15:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2648.86000 dir=SHORT |
| 11986 | 2024-11-20T17:30:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |
| 13289 | 2024-12-11T03:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2701.10000 dir=SHORT |
| 13290 | 2024-12-11T03:15:00 | SWEEP→EXPANSION | SWEEP | Shadow resume: displacement carried from prior HTF window — strength check skipped |

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

