# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T14:56:00.540109
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
- Resolver lifecycle resets: HTF=**11,244** gap=**97** forced=**82**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 36,954 | 35,130 | 35,159 |
| SWEEP | 7,412 | 6,996 | 6,987 |
| DISPLACEMENT | 381 | 373 | 373 |
| EXPANSION | 2,337 | 4,625 | 4,605 |
| RETEST | 105 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 8 | 51 | 51 |

## Agreement

- **Exact bar match:** 44,007 / 47,197 (**93.24%**)
- **Mismatch bars:** 3,190 (6.76%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **34781** | 2 | 0 | 325 | 22 | 0 | 0 | 35,130 |
| **SWEEP** | 58 | **6900** | 0 | 37 | 1 | 0 | 0 | 6,996 |
| **DISPLACEMENT** | 0 | 0 | **356** | 17 | 0 | 0 | 0 | 373 |
| **EXPANSION** | 2112 | 469 | 25 | **1951** | 66 | 0 | 2 | 4,625 |
| **RETEST** | 2 | 1 | 0 | 1 | **13** | 0 | 0 | 17 |
| **EXECUTION** | 1 | 0 | 0 | 1 | 3 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 0 | 40 | 0 | 5 | 0 | 0 | **6** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| EXPANSION | RANGE | 2,112 | 66.21% |
| EXPANSION | SWEEP | 469 | 14.70% |
| RANGE | EXPANSION | 325 | 10.19% |
| EXPANSION | RETEST | 66 | 2.07% |
| SWEEP | RANGE | 58 | 1.82% |
| SHADOW_PENDING | SWEEP | 40 | 1.25% |
| SWEEP | EXPANSION | 37 | 1.16% |
| EXPANSION | DISPLACEMENT | 25 | 0.78% |
| RANGE | RETEST | 22 | 0.69% |
| DISPLACEMENT | EXPANSION | 17 | 0.53% |
| SHADOW_PENDING | EXPANSION | 5 | 0.16% |
| EXECUTION | RETEST | 3 | 0.09% |
| RETEST | RANGE | 2 | 0.06% |
| EXPANSION | SHADOW_PENDING | 2 | 0.06% |
| RANGE | SWEEP | 2 | 0.06% |
| RETEST | SWEEP | 1 | 0.03% |
| EXECUTION | RANGE | 1 | 0.03% |
| SWEEP | RETEST | 1 | 0.03% |
| RETEST | EXPANSION | 1 | 0.03% |
| EXECUTION | EXPANSION | 1 | 0.03% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 392 | 392 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 485 | 490 | 6 | RANGE | EXPANSION | 3 |
| 793 | 793 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 903 | 1140 | 238 | EXPANSION | RANGE | 184 |
| 1681 | 1681 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 1702 | 1702 | 1 | EXECUTION | RETEST | 1 |
| 1802 | 1802 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 2618 | 2633 | 16 | RANGE | EXPANSION | 12 |
| 2704 | 2704 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 3119 | 3130 | 12 | EXPANSION | RANGE | 7 |
| 3534 | 3542 | 9 | RANGE | EXPANSION | 5 |
| 3573 | 3573 | 1 | DISPLACEMENT | EXPANSION | 1 |
| 4541 | 4544 | 4 | RANGE | RETEST | 2 |
| 4802 | 4845 | 44 | EXPANSION | RANGE | 37 |
| 5086 | 5089 | 4 | RANGE | EXPANSION | 2 |
| 5092 | 5305 | 214 | EXPANSION | RANGE | 167 |
| 7102 | 7106 | 5 | RANGE | EXPANSION | 2 |
| 7470 | 7482 | 13 | RANGE | EXPANSION | 9 |
| 7830 | 7846 | 17 | RANGE | EXPANSION | 14 |
| 8181 | 8186 | 6 | RANGE | EXPANSION | 3 |
| 8568 | 8568 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 8574 | 8575 | 2 | EXECUTION | RETEST | 1 |
| 9196 | 9196 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 9496 | 9496 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 10274 | 10276 | 3 | DISPLACEMENT | EXPANSION | 1 |
| 10300 | 10355 | 56 | EXPANSION | RANGE | 45 |
| 11932 | 11932 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 11985 | 11985 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 12068 | 12195 | 128 | EXPANSION | RANGE | 102 |
| 12434 | 12442 | 9 | RANGE | EXPANSION | 5 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **132**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| SHADOW_PENDING | SWEEP | EXPANSION | 43 |
| RANGE | SHADOW_PENDING | SWEEP | 40 |
| RANGE | SWEEP | RANGE | 28 |
| SWEEP | DISPLACEMENT | EXPANSION | 6 |
| RANGE | SHADOW_PENDING | EXPANSION | 5 |
| RETEST | EXECUTION | RETEST | 3 |
| EXPANSION | RETEST | RANGE | 2 |
| EXPANSION | RETEST | SWEEP | 1 |
| EXECUTION | RESOLUTION | RANGE | 1 |
| RETEST | EXECUTION | RANGE | 1 |
| EXPANSION | RETEST | EXPANSION | 1 |
| RETEST | EXECUTION | EXPANSION | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 392 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 393 | 2024-05-28T09:45:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=316 |
| 490 | 2024-05-29T11:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2348.86000 idx=416 |
| 793 | 2024-06-03T17:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2345.34000 dir=SHORT |
| 794 | 2024-06-03T18:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=716 |
| 1140 | 2024-06-07T12:30:00 | EXPANSION→RETEST | SWEEP | Retest | depth_abs=1.90000 ceiling=2.54100 |
| 1681 | 2024-06-17T09:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2316.56000 dir=LONG |
| 1682 | 2024-06-17T10:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=1603 |
| 1702 | 2024-06-17T15:00:00 | RETEST→EXECUTION | RETEST | Risk approved → entering execution |
| 1703 | 2024-06-17T15:15:00 | EXECUTION→RESOLUTION | RANGE | Trade closed: TP1 |
| 1802 | 2024-06-18T17:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2327.11000 dir=SHORT |
| 2704 | 2024-07-02T15:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2319.07000 dir=LONG |
| 2705 | 2024-07-02T15:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=2628 |
| 3118 | 2024-07-09T06:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=3040 |
| 3129 | 2024-07-09T08:45:00 | EXPANSION→RETEST | RANGE | Retest | depth_abs=0.75000 ceiling=0.82800 |
| 3130 | 2024-07-09T09:00:00 | RETEST→EXECUTION | RANGE | Risk approved → entering execution |
| 3540 | 2024-07-15T19:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2439.78000 idx=3466 |
| 3573 | 2024-07-16T04:45:00 | SWEEP→DISPLACEMENT | EXPANSION | Displacement | body_ratio=0.746 wick=2.80000 |
| 5089 | 2024-08-07T15:45:00 | RANGE→SHADOW_PENDING | EXPANSION | Shadow resume: confirming sweep @ 2407.06000 dir=SHORT |
| 5090 | 2024-08-07T16:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=5011 |
| 7105 | 2024-09-06T16:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2506.78000 idx=7031 |
| 7480 | 2024-09-12T18:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2555.21000 idx=7406 |
| 7845 | 2024-09-18T17:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2568.10000 idx=7771 |
| 8186 | 2024-09-24T10:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2622.68000 idx=8112 |
| 8568 | 2024-09-30T14:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2634.50000 dir=LONG |
| 8569 | 2024-09-30T14:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=8492 |
| 8574 | 2024-09-30T15:30:00 | RETEST→EXECUTION | RETEST | Risk approved → entering execution |
| 9196 | 2024-10-09T10:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2609.18000 dir=LONG |
| 9197 | 2024-10-09T10:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=9120 |
| 9496 | 2024-10-14T16:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2648.44000 dir=LONG |
| 9497 | 2024-10-14T16:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=9420 |
| 10276 | 2024-10-25T04:00:00 | RANGE→SHADOW_PENDING | EXPANSION | Shadow resume: confirming sweep @ 2731.29000 dir=LONG |
| 10277 | 2024-10-25T04:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=10199 |
| 11932 | 2024-11-20T04:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2641.70000 dir=SHORT |
| 11933 | 2024-11-20T04:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=11856 |
| 11985 | 2024-11-20T17:15:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2648.86000 dir=SHORT |
| 11986 | 2024-11-20T17:30:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=11908 |
| 12785 | 2024-12-03T15:00:00 | RANGE→SWEEP | RANGE | Sweep @ 2637.78000 idx=12711 |
| 13289 | 2024-12-11T03:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2701.10000 dir=SHORT |
| 13290 | 2024-12-11T03:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=13212 |

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

