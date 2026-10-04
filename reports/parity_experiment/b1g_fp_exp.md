# CRT State Resolver — Bar-Aligned Confusion Matrix

> Generated: 2026-08-05T15:15:05.542338
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
- Resolver lifecycle resets: HTF=**10,626** gap=**112** forced=**82**
- **HTF mode:** `engine` (instrument=`XAUUSD`, window=4)
- HTF phase-lock: unique ids=**11,800**, changes on resolved slice=**11,799**, range `XAUUSD-HTF-000019` → `XAUUSD-HTF-011818`

| State | Resolver | Engine (aligned) | Reference |
|-------|----------|------------------|-----------|
| RANGE | 35,019 | 35,130 | 35,159 |
| SWEEP | 7,016 | 6,996 | 6,987 |
| DISPLACEMENT | 362 | 373 | 373 |
| EXPANSION | 4,768 | 4,625 | 4,605 |
| RETEST | 26 | 17 | 17 |
| EXECUTION | 0 | 5 | 5 |
| SHADOW_PENDING | 6 | 51 | 51 |

## Agreement

- **Exact bar match:** 46,979 / 47,197 (**99.54%**)
- **Mismatch bars:** 218 (0.46%)

## Confusion matrix

Rows = **engine** state; columns = **resolver** state.

| eng\res | RANGE | SWEEP | DISPLACEMENT | EXPANSION | RETEST | EXECUTION | SHADOW_PENDING | row sum |
|---------|------|------|------|------|------|------|------|---------|
| **RANGE** | **34996** | 2 | 0 | 128 | 4 | 0 | 0 | 35,130 |
| **SWEEP** | 23 | **6973** | 0 | 0 | 0 | 0 | 0 | 6,996 |
| **DISPLACEMENT** | 0 | 0 | **362** | 11 | 0 | 0 | 0 | 373 |
| **EXPANSION** | 0 | 0 | 0 | **4625** | 0 | 0 | 0 | 4,625 |
| **RETEST** | 0 | 0 | 0 | 0 | **17** | 0 | 0 | 17 |
| **EXECUTION** | 0 | 0 | 0 | 0 | 5 | **0** | 0 | 5 |
| **SHADOW_PENDING** | 0 | 41 | 0 | 4 | 0 | 0 | **6** | 51 |

### Top off-diagonal confusions (engine → resolver mislabel)

| Engine | Resolver | N | % of mismatches |
|--------|----------|---|-----------------|
| RANGE | EXPANSION | 128 | 58.72% |
| SHADOW_PENDING | SWEEP | 41 | 18.81% |
| SWEEP | RANGE | 23 | 10.55% |
| DISPLACEMENT | EXPANSION | 11 | 5.05% |
| EXECUTION | RETEST | 5 | 2.29% |
| RANGE | RETEST | 4 | 1.83% |
| SHADOW_PENDING | EXPANSION | 4 | 1.83% |
| RANGE | SWEEP | 2 | 0.92% |

## Divergence episodes (contiguous mismatch runs)

First episodes by timeline order (capped).

| Start idx | End idx | Len | Dominant engine | Dominant resolver | Dom N |
|-----------|---------|-----|-----------------|-------------------|-------|
| 392 | 392 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 793 | 793 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 1681 | 1681 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 1702 | 1702 | 1 | EXECUTION | RETEST | 1 |
| 1802 | 1802 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 2704 | 2704 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 3130 | 3131 | 2 | EXECUTION | RETEST | 1 |
| 3133 | 3134 | 2 | SWEEP | RANGE | 2 |
| 3534 | 3542 | 9 | RANGE | EXPANSION | 5 |
| 5086 | 5089 | 4 | RANGE | EXPANSION | 2 |
| 7830 | 7846 | 17 | RANGE | EXPANSION | 14 |
| 8568 | 8568 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 8574 | 8575 | 2 | EXECUTION | RETEST | 1 |
| 9196 | 9196 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 9496 | 9496 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 10274 | 10276 | 3 | DISPLACEMENT | EXPANSION | 1 |
| 10356 | 10356 | 1 | RANGE | SWEEP | 1 |
| 11932 | 11932 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 11985 | 11985 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 12198 | 12198 | 1 | RANGE | SWEEP | 1 |
| 13289 | 13289 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 13988 | 13988 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 14501 | 14501 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 16154 | 16154 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 16176 | 16176 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 16776 | 16776 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 17178 | 17189 | 12 | RANGE | EXPANSION | 9 |
| 19472 | 19472 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 19588 | 19588 | 1 | SHADOW_PENDING | SWEEP | 1 |
| 19781 | 19782 | 2 | SWEEP | RANGE | 2 |

## Engine transition edges where resolver disagreed

At each `STATE_TRANSITION` candle_index, compare engine `state_to` vs resolver state.

- Total disagreeing transition edges: **104**

| Engine from | Engine to | Resolver at bar | N |
|-------------|-----------|-----------------|---|
| SHADOW_PENDING | SWEEP | EXPANSION | 43 |
| RANGE | SHADOW_PENDING | SWEEP | 41 |
| RANGE | SWEEP | RANGE | 10 |
| RETEST | EXECUTION | RETEST | 5 |
| RANGE | SHADOW_PENDING | EXPANSION | 4 |
| EXECUTION | RESOLUTION | RANGE | 1 |

### Sample mismatches (first 40)

| Idx | Time | Engine | Resolver | Reason |
|-----|------|--------|----------|--------|
| 392 | 2024-05-28T09:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2341.83000 dir=LONG |
| 393 | 2024-05-28T09:45:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=316 |
| 793 | 2024-06-03T17:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2345.34000 dir=SHORT |
| 794 | 2024-06-03T18:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=716 |
| 1681 | 2024-06-17T09:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2316.56000 dir=LONG |
| 1682 | 2024-06-17T10:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=1603 |
| 1702 | 2024-06-17T15:00:00 | RETEST→EXECUTION | RETEST | Risk approved → entering execution |
| 1703 | 2024-06-17T15:15:00 | EXECUTION→RESOLUTION | RANGE | Trade closed: TP1 |
| 1802 | 2024-06-18T17:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2327.11000 dir=SHORT |
| 2704 | 2024-07-02T15:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2319.07000 dir=LONG |
| 2705 | 2024-07-02T15:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=2628 |
| 3118 | 2024-07-09T06:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=3040 |
| 3130 | 2024-07-09T09:00:00 | RETEST→EXECUTION | RETEST | Risk approved → entering execution |
| 3133 | 2024-07-09T09:45:00 | RANGE→SWEEP | RANGE | Sweep @ 2362.81000 idx=3059 |
| 3540 | 2024-07-15T19:30:00 | RANGE→SWEEP | RANGE | Sweep @ 2439.78000 idx=3466 |
| 5089 | 2024-08-07T15:45:00 | RANGE→SHADOW_PENDING | EXPANSION | Shadow resume: confirming sweep @ 2407.06000 dir=SHORT |
| 5090 | 2024-08-07T16:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=5011 |
| 7845 | 2024-09-18T17:15:00 | RANGE→SWEEP | RANGE | Sweep @ 2568.10000 idx=7771 |
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
| 13289 | 2024-12-11T03:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2701.10000 dir=SHORT |
| 13290 | 2024-12-11T03:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=13212 |
| 13988 | 2024-12-20T16:45:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2618.39000 dir=SHORT |
| 13989 | 2024-12-20T17:00:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=13911 |
| 14501 | 2024-12-31T10:15:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2615.00000 dir=SHORT |
| 14502 | 2024-12-31T10:30:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=14424 |
| 15145 | 2025-01-10T10:15:00 | SHADOW_PENDING→SWEEP | EXPANSION | Shadow: prior-window displacement restored from idx=15068 |
| 16154 | 2025-01-27T12:00:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2765.62000 dir=SHORT |
| 16176 | 2025-01-27T17:30:00 | RANGE→SHADOW_PENDING | SWEEP | Shadow resume: confirming sweep @ 2739.55000 dir=LONG |

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

