# Run story — `run_20260909_202201`

**Parent run:** `run_20260909_202201` · **source run (dual-construction object):** `run_20260906_013609`
**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none · no promotion

This is the DeepSeek-lane story of the run, told from the moment each of the **69**
`HTF_CHANGED_WHILE_DISPLACEMENT` pending-memory **CREATE** is born — with the raw **OHLC** bar and the
full **feature/state bundle** at that candle — through its lifecycle to its **end**
(`EXPIRED_TTL` / `CLEARED` / `RESTORED→EXPANSION`), and onto its forward outcomes
**H20 · H40 · H60 · H80 · H100** vs the **Always-Long** control.

## Standing contract (frozen)

| Term | Value |
|---|---|
| Unit | CREATE of HTF-displacement pending memory (n=69), NOT SHADOW→EXP restore (n=6) |
| Corpus | Phase-1 XAUUSD · csv sha256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Cost | SEM-015 TIMEOUT (component_measured.v1, MEASURED) |
| Horizon | H20 (also reported H40/H60/H80/H100) |
| Control | Always-Long (stride H20, same creates) |
| Config | `v2_htfcrt_2026_08` · source object config `v4_dual_construction_2026_09` |

**Object under the microscope:** unresolved HTF displacement memory, preserved through RANGE,
reactivated by a matching sweep (`sweep.dir == pending_dir`) before TTL expiry → shadow-resume
EXPANSION (strength skipped).

## The cast — 69 creates, in order of birth

`2024-06-07 11:15` … `2026-05-19 11:00`. Every row is one candle at the moment memory is created:
`OHLC` = open/high/low/close of that bar · `sess` = broker-local hour session · `CRT` = parent CRT
track · `T1/T3` = resolver-vs-engine state agree/disagree · `mem` = `pending_dir` (what the memory
remembers) / `tb` = `trend_bias` sign · `ATR` = live ATR · `fate` = final outcome at `closed_idx`
(age) · `H20` / `H100` = `memory_dir_H20` / `memory_dir_H100` net return (R) vs the same-bar
Always-Long control.

Fates: **45 EXPIRED_TTL · 18 CLEARED_OR_OVERWRITTEN · 6 RESTORED_TO_EXPANSION** (funnel 69 → 45 → 17
clear + 1 overwrite → 6 restore).

> Full per-row record with every field (including forward H20–H100 and MFE/MAE):
> `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/story_rows.json`
## The chronicle — all 69, beat by beat

`H20` / `H100` columns are `memory_dir` net return (R) vs the same-bar Always-Long control (the
control value is subtracted, so a `+` means the memory direction beat drift; `NA` = that create had
no `pending_dir` — a non-HTF reset, so it is unscored on the memory arm).

### Part 1 — 2024 (17 creates)

| TS | c | OHLC o/h/l/c | session | parent CRT | T1/T3 | mem/tb | ATR | fate@close(age) | H20 | H100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2024-06-07 11:15:00 | 1073 | 2351/2358/2351/2353 | NY_17_22 | RANGE_C1 | DISAGREE | SHORT/LONG | 5.5 | EXPIRED_TTL@1077(age=1) | -0.31 | +12.36 |
| 2024-06-12 10:15:00 | 1345 | 2315/2315/2312/2312 | NY_17_22 | DISTRIBUTION_C3 | AGREE | SHORT/LONG | 4.1 | CLEARED_OR_OVERWRITTEN | -0.20 | -5.72 |
| 2024-06-13 15:15:00 | 1457 | 2307/2308/2306/2308 | OFFHOURS_22_24 | RANGE_C1 | AGREE | SHORT/SHORT | 4.8 | RESTORED_TO_EXPANSION@1459(age=3) | +1.72 | +3.74 |
| 2024-06-25 17:45:00 | 2193 | 2325/2327/2324/2327 | ASIA_0_8 | RANGE_C1 | AGREE | LONG/SHORT | 1.3 | RESTORED_TO_EXPANSION@2197(age=4) | -3.64 | -9.10 |
| 2024-06-27 03:45:00 | 2321 | 2300/2300/2298/2299 | LONDON_8_13 | DISTRIBUTION_C3 | AGREE | LONG/SHORT | 3.0 | RESTORED_TO_EXPANSION@2325(age=3) | -6.88 | -1.31 |
| 2024-09-09 08:45:00 | 7105 | 2491/2492/2488/2488 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | DISAGREE | SHORT/SHORT | 5.3 | CLEARED_OR_OVERWRITTEN | +2.35 | +2.55 |
| 2024-10-14 05:45:00 | 9393 | 2653/2655/2652/2655 | LONDON_NY_OVERLAP_13_17 | MANIPULATION_C2 | DISAGREE | LONG/SHORT | 2.6 | EXPIRED_TTL@9397(age=1) | +7.63 | +5.97 |
| 2024-10-15 22:45:00 | 9553 | 2662/2662/2659/2662 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/SHORT | 2.7 | EXPIRED_TTL@9557(age=1) | -3.44 | -12.35 |
| 2024-11-04 08:45:00 | 10785 | 2738/2742/2738/2741 | LONDON_NY_OVERLAP_13_17 | MANIPULATION_C2 | DISAGREE | SHORT/LONG | 4.4 | RESTORED_TO_EXPANSION@10787(age=3) | +3.70 | +3.56 |
| 2024-11-05 09:45:00 | 10881 | 2736/2737/2735/2736 | NY_17_22 | RANGE_C1 | DISAGREE | SHORT/LONG | 3.8 | EXPIRED_TTL@10885(age=1) | +0.79 | -0.49 |
| 2024-11-13 11:45:00 | 11441 | 2610/2611/2608/2609 | NY_17_22 | MANIPULATION_C2 | AGREE | LONG/SHORT | 5.2 | EXPIRED_TTL@11445(age=5) | +0.78 | -1.92 |
| 2024-11-27 17:45:00 | 12385 | 2640/2645/2640/2643 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 2.0 | EXPIRED_TTL@12389(age=3) | -5.40 | +0.80 |
| 2024-12-03 10:30:00 | 12705 | 2640/2642/2640/2641 | NY_17_22 | RANGE_C1 | AGREE | SHORT/LONG | 5.0 | EXPIRED_TTL@12709(age=2) | +0.13 | -1.28 |
| 2024-12-09 02:30:00 | 13041 | 2631/2631/2628/2629 | LONDON_8_13 | RANGE_C1 | DISAGREE | SHORT/LONG | 2.8 | EXPIRED_TTL@13045(age=1) | +1.40 | -5.86 |
| 2024-12-17 16:30:00 | 13649 | 2641/2642/2638/2639 | ASIA_0_8 | RANGE_C1 | AGREE | LONG/SHORT | 1.4 | EXPIRED_TTL@13653(age=1) | +1.58 | -1.40 |
| 2024-12-23 04:30:00 | 13969 | 2624/2626/2624/2626 | LONDON_8_13 | RANGE_C1 | AGREE | LONG/LONG | 2.6 | CLEARED_OR_OVERWRITTEN | +6.51 | +5.09 |
| 2024-12-26 09:45:00 | 14161 | 2624/2626/2624/2625 | LONDON_NY_OVERLAP_13_17 | MANIPULATION_C2 | AGREE | SHORT/SHORT | 2.2 | EXPIRED_TTL@14165(age=2) | -0.34 | -6.13 |
### Part 2 — 2025 H1 (creates 18–36)

| TS | c | OHLC o/h/l/c | session | parent CRT | T1/T3 | mem/tb | ATR | fate@close(age) | H20 | H100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-01-17 20:45:00 | 15585 | 2708/2708/2705/2706 | ASIA_0_8 | DISTRIBUTION_C3 | AGREE | SHORT/LONG | 2.2 | CLEARED_OR_OVERWRITTEN | +2.09 | +4.13 |
| 2025-01-31 09:15:00 | 16449 | 2796/2800/2796/2800 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | AGREE | LONG/LONG | 3.4 | CLEARED_OR_OVERWRITTEN | +1.63 | +5.81 |
| 2025-02-03 06:15:00 | 16529 | 2783/2783/2779/2779 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | DISAGREE | LONG/LONG | 2.6 | EXPIRED_TTL@16533(age=1) | +2.67 | +4.04 |
| 2025-02-05 04:15:00 | 16705 | 2852/2853/2851/2851 | LONDON_8_13 | MANIPULATION_C2 | AGREE | LONG/LONG | 3.8 | EXPIRED_TTL@16709(age=1) | +4.75 | +12.60 |
| 2025-02-06 17:15:00 | 16849 | 2844/2848/2844/2845 | ASIA_0_8 | MANIPULATION_C2 | AGREE | SHORT/SHORT | 3.2 | EXPIRED_TTL@16853(age=2) | +0.12 | +0.84 |
| 2025-02-07 18:15:00 | 16945 | 2871/2872/2866/2869 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 1.5 | EXPIRED_TTL@16949(age=1) | -2.67 | -10.22 |
| 2025-04-01 09:45:00 | 20305 | 3133/3137/3132/3134 | NY_17_22 | RANGE_C1 | AGREE | SHORT/SHORT | 6.7 | EXPIRED_TTL@20309(age=4) | -1.45 | +0.68 |
| 2025-04-10 04:45:00 | 20929 | 3088/3096/3085/3094 | LONDON_8_13 | RANGE_C1 | AGREE | SHORT/LONG | 8.8 | EXPIRED_TTL@20933(age=3) | -4.55 | -8.98 |
| 2025-04-10 16:45:00 | 20977 | 3122/3128/3116/3117 | ASIA_0_8 | MANIPULATION_C2 | AGREE | SHORT/LONG | 11.6 | EXPIRED_TTL@20981(age=1) | -3.92 | -10.03 |
| 2025-04-11 13:45:00 | 21057 | 3216/3217/3210/3213 | NY_17_22 | RANGE_C1 | AGREE | SHORT/LONG | 8.3 | EXPIRED_TTL@21061(age=1) | -3.66 | -8.47 |
| 2025-04-17 05:45:00 | 21393 | 3332/3341/3330/3340 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | DISAGREE | LONG/LONG | 8.2 | EXPIRED_TTL@21397(age=3) | +1.19 | +2.65 |
| 2025-05-14 03:45:00 | 23041 | 3245/3246/3241/3244 | LONDON_8_13 | RANGE_C1 | AGREE | SHORT/LONG | 6.1 | CLEARED_OR_OVERWRITTEN | +1.53 | +3.40 |
| 2025-05-15 04:45:00 | 23137 | 3178/3180/3171/3172 | LONDON_8_13 | RANGE_C1 | DISAGREE | SHORT/SHORT | 5.8 | CLEARED_OR_OVERWRITTEN | +7.82 | +9.48 |
| 2025-05-26 15:45:00 | 23825 | 3334/3335/3332/3334 | OFFHOURS_22_24 | MANIPULATION_C2 | AGREE | LONG/LONG | 3.5 | CLEARED_OR_OVERWRITTEN | -3.75 | -7.19 |
| 2025-06-03 16:15:00 | 24369 | 3360/3362/3358/3360 | OFFHOURS_22_24 | RANGE_C1 | AGREE | LONG/LONG | 2.8 | RESTORED_TO_EXPANSION@24371(age=3) | -5.60 | -8.77 |
| 2025-06-04 17:15:00 | 24465 | 3367/3370/3364/3370 | ASIA_0_8 | RANGE_C1 | DISAGREE | LONG/LONG | 2.0 | EXPIRED_TTL@24469(age=1) | +0.85 | +11.62 |
| 2025-06-06 11:15:00 | 24625 | 3359/3365/3358/3364 | NY_17_22 | RANGE_C1 | DISAGREE | SHORT/SHORT | 10.8 | EXPIRED_TTL@24629(age=7) | -0.74 | +1.93 |
| 2025-06-10 17:15:00 | 24833 | 3336/3339/3331/3334 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/SHORT | 3.1 | CLEARED_OR_OVERWRITTEN | +5.10 | -2.95 |
| 2025-06-16 17:15:00 | 25201 | 3397/3399/3392/3392 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 5.7 | EXPIRED_TTL@25205(age=2) | +2.89 | +9.37 |
### Part 3 — 2025 H2 (creates 37–50)

| TS | c | OHLC o/h/l/c | session | parent CRT | T1/T3 | mem/tb | ATR | fate@close(age) | H20 | H100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-06-23 04:45:00 | 25601 | 3358/3358/3354/3355 | LONDON_8_13 | MANIPULATION_C2 | AGREE | SHORT/LONG | 4.8 | EXPIRED_TTL@25605(age=2) | -2.54 | -4.64 |
| 2025-06-23 20:45:00 | 25665 | 3382/3384/3380/3383 | ASIA_0_8 | MANIPULATION_C2 | AGREE | SHORT/SHORT | 6.3 | EXPIRED_TTL@25669(age=2) | +1.05 | +2.23 |
| 2025-06-26 23:45:00 | 25953 | 3329/3330/3328/3328 | LONDON_8_13 | DISTRIBUTION_C3 | AGREE | SHORT/LONG | 3.0 | EXPIRED_TTL@25957(age=7) | -2.16 | +15.10 |
| 2025-08-04 10:45:00 | 28369 | 3355/3356/3354/3356 | NY_17_22 | RANGE_C1 | DISAGREE | SHORT/LONG | 9.9 | EXPIRED_TTL@28373(age=2) | -1.13 | -2.34 |
| 2025-08-08 06:45:00 | 28721 | 3396/3397/3394/3396 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | AGREE | LONG/SHORT | 6.1 | CLEARED_OR_OVERWRITTEN | +1.22 | +1.61 |
| 2025-08-26 10:45:00 | 29841 | 3378/3379/3376/3377 | NY_17_22 | MANIPULATION_C2 | DISAGREE | LONG/LONG | 3.2 | CLEARED_OR_OVERWRITTEN | -2.91 | +2.97 |
| 2025-09-08 10:15:00 | 30657 | 3605/3610/3605/3609 | NY_17_22 | RANGE_C1 | DISAGREE | LONG/LONG | 10.9 | CLEARED_OR_OVERWRITTEN | +0.39 | +4.60 |
| 2025-09-23 05:15:00 | 31649 | 3744/3745/3741/3743 | LONDON_8_13 | RANGE_C1 | AGREE | SHORT/LONG | 5.1 | CLEARED_OR_OVERWRITTEN | -0.56 | -11.77 |
| 2025-09-30 18:15:00 | 32161 | 3835/3840/3831/3835 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 3.1 | EXPIRED_TTL@32165(age=1) | -11.14 | -11.74 |
| 2025-11-27 08:15:00 | 35985 | 4153/4157/4152/4157 | LONDON_NY_OVERLAP_13_17 | MANIPULATION_C2 | AGREE | LONG/SHORT | 7.7 | CLEARED_OR_OVERWRITTEN | +1.43 | +0.55 |
| 2025-11-27 12:15:00 | 36001 | 4156/4157/4153/4153 | NY_17_22 | RANGE_C1 | AGREE | SHORT/LONG | 6.8 | EXPIRED_TTL@36005(age=5) | +0.31 | +0.61 |
| 2025-12-03 13:00:00 | 36353 | 4201/4201/4197/4200 | NY_17_22 | MANIPULATION_C2 | AGREE | LONG/SHORT | 10.3 | EXPIRED_TTL@36357(age=3) | +1.88 | +2.07 |
| 2025-12-05 19:00:00 | 36561 | 4214/4218/4211/4215 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/SHORT | 4.0 | EXPIRED_TTL@36565(age=4) | -6.75 | -2.41 |
| 2025-12-18 16:00:00 | 37377 | 4337/4341/4333/4336 | OFFHOURS_22_24 | RANGE_C1 | AGREE | LONG/LONG | 5.8 | RESTORED_TO_EXPANSION@37381(age=2) | -1.33 | -1.99 |
### Part 4 — 2026 (creates 51–69)

| TS | c | OHLC o/h/l/c | session | parent CRT | T1/T3 | mem/tb | ATR | fate@close(age) | H20 | H100 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-12-18 20:00:00 | 37393 | 4333/4341/4332/4339 | ASIA_0_8 | MANIPULATION_C2 | AGREE | SHORT/SHORT | 5.0 | EXPIRED_TTL@37397(age=4) | +0.09 | +2.68 |
| 2025-12-19 21:00:00 | 37489 | 4349/4351/4347/4347 | ASIA_0_8 | MANIPULATION_C2 | AGREE | SHORT/SHORT | 7.1 | EXPIRED_TTL@37493(age=2) | -1.22 | -11.64 |
| 2025-12-22 02:00:00 | 37505 | 4355/4365/4355/4360 | LONDON_8_13 | DISTRIBUTION_C3 | AGREE | NA/LONG | 4.4 | CLEARED_OR_OVERWRITTEN | NA | NA |
| 2025-12-30 14:15:00 | 38001 | 4396/4399/4392/4394 | NY_17_22 | RANGE_C1 | AGREE | LONG/SHORT | 9.9 | EXPIRED_TTL@38005(age=1) | +2.31 | +0.14 |
| 2026-01-07 03:15:00 | 38417 | 4471/4479/4471/4477 | LONDON_8_13 | DISTRIBUTION_C3 | AGREE | NA/LONG | 8.0 | CLEARED_OR_OVERWRITTEN | NA | NA |
| 2026-01-15 01:15:00 | 38961 | 4616/4619/4606/4609 | LONDON_8_13 | MANIPULATION_C2 | AGREE | NA/LONG | 8.0 | CLEARED_OR_OVERWRITTEN | NA | NA |
| 2026-01-20 02:45:00 | 39233 | 4663/4664/4660/4660 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 6.2 | EXPIRED_TTL@39237(age=2) | +0.98 | -9.42 |
| 2026-01-20 22:45:00 | 39313 | 4750/4758/4749/4757 | ASIA_0_8 | DISTRIBUTION_C3 | AGREE | SHORT/LONG | 6.0 | EXPIRED_TTL@39317(age=2) | -5.32 | -25.36 |
| 2026-01-22 16:45:00 | 39473 | 4846/4847/4835/4835 | ASIA_0_8 | RANGE_C1 | AGREE | LONG/SHORT | 22.6 | EXPIRED_TTL@39477(age=1) | +0.03 | +6.73 |
| 2026-01-28 20:45:00 | 39857 | 5274/5284/5272/5282 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 15.9 | EXPIRED_TTL@39861(age=1) | -3.91 | -19.14 |
| 2026-02-02 15:45:00 | 40113 | 4686/4722/4684/4706 | OFFHOURS_22_24 | RANGE_C1 | AGREE | SHORT/SHORT | 66.7 | EXPIRED_TTL@40117(age=1) | +2.68 | +0.81 |
| 2026-02-02 19:45:00 | 40129 | 4675/4689/4663/4674 | ASIA_0_8 | RANGE_C1 | AGREE | LONG/SHORT | 78.0 | EXPIRED_TTL@40133(age=7) | -2.30 | +0.85 |
| 2026-02-20 04:15:00 | 41345 | 4997/4999/4993/4997 | LONDON_8_13 | DISTRIBUTION_C3 | DISAGREE | SHORT/LONG | 8.6 | EXPIRED_TTL@41349(age=4) | -1.18 | -2.55 |
| 2026-03-10 16:15:00 | 42497 | 5201/5229/5199/5222 | OFFHOURS_22_24 | RANGE_C1 | AGREE | LONG/LONG | 11.0 | EXPIRED_TTL@42501(age=1) | +2.29 | +5.15 |
| 2026-04-15 19:00:00 | 44801 | 4802/4811/4800/4808 | ASIA_0_8 | RANGE_C1 | AGREE | SHORT/LONG | 7.1 | EXPIRED_TTL@44805(age=3) | +1.83 | +1.78 |
| 2026-05-05 17:00:00 | 46081 | 4579/4584/4571/4574 | ASIA_0_8 | RANGE_C1 | AGREE | NA/SHORT | 6.4 | CLEARED_OR_OVERWRITTEN | NA | NA |
| 2026-05-06 02:00:00 | 46113 | 4573/4591/4569/4589 | LONDON_8_13 | RANGE_C1 | AGREE | LONG/LONG | 7.4 | EXPIRED_TTL@46117(age=1) | +2.31 | +17.67 |
| 2026-05-14 08:00:00 | 46689 | 4703/4704/4700/4700 | LONDON_NY_OVERLAP_13_17 | RANGE_C1 | AGREE | LONG/SHORT | 8.0 | EXPIRED_TTL@46693(age=3) | +1.00 | +0.48 |
| 2026-05-19 11:00:00 | 46977 | 4557/4559/4543/4546 | NY_17_22 | RANGE_C1 | AGREE | LONG/SHORT | 14.6 | EXPIRED_TTL@46981(age=1) | +1.75 | -2.36 |
---

## Deep-dive A — the signal-carrying state bundle

Across all 69, only three **pre-trade state** tags show positive expectancy vs the Always-Long
control (H20, `memory_dir`):

| Bundle | n | E | E_AL | lift | PF | power |
|---|---:|---:|---:|---:|---:|---:|
| t1_t3 = DISAGREE | 15 | +1.5017 | -0.2505 | **+1.7522** | 4.591 | INSUFFICIENT |
| session = LONDON_NY_OVERLAP_13_17 | 10 | +2.2483 | +1.0606 | **+1.1877** | 68.0 | INSUFFICIENT |
| atr_tercile = T2_MID | 20 | +0.2897 | -0.1563 | +0.4459 | 1.314 | INSUFFICIENT |

The co-occurrence that stands out (the **economic knot** of this run):

| Created idx | TS | OHLC | T1/T3 | session | mem/tb | fate | H20 | H100 |
|---|---|---|---|---|---|---|---|---|
| 7105 | 2024-09-09 08:45 | 2491/2492/2488/2488 | DISAGREE | OVERLAP | SHORT/SHORT | CLEARED | +2.35 | +2.55 |
| 9393 | 2024-10-14 05:45 | 2653/2655/2652/2655 | DISAGREE | OVERLAP | LONG/SHORT | EXPIRED | +7.63 | +5.97 |
| 10785 | 2024-11-04 08:45 | 2738/2742/2738/2741 | DISAGREE | OVERLAP | SHORT/LONG | RESTORED | +3.70 | +3.56 |
| 16529 | 2025-02-03 06:15 | 2783/2783/2779/2779 | DISAGREE | OVERLAP | LONG/LONG | EXPIRED | +2.67 | +4.04 |
| 21393 | 2025-04-17 05:45 | 3332/3341/3330/3340 | DISAGREE | OVERLAP | LONG/LONG | EXPIRED | +1.19 | +2.65 |

**DISAGREE × LONDON_NY_OVERLAP:** n=5, mean `memory_dir_H20` = **+3.5086** — the strongest
pre-trade bundle mean in the whole run. Every one of the 5 is positive at both H20 and H100.

**Self-correction (evidence honesty):** the two rows with the *largest* lift in the ranked census —
`outcome=CLEARED_OR_OVERWRITTEN` (+2.328) and `outcome=RESTORED_TO_EXPANSION` (+1.844) — are
**post-hoc funnel fates, not pre-trade selectable state.** A create's ending is not a condition an
entry can pick; ranking them as the signal would be fitting the outcome to itself. So those are
diagnostics, excluded from the signal bundle.

**Power honesty (the binding constraint):** every positive-lift cell here is **n < 30 →
INSUFFICIENT.** The only n ≥ 30 cells (AGREE n=50, RANGE_C1 n=45, EXPIRED_TTL n=45, pending_SHORT
n=39, age_1 n=30) all carry **negative** lift. The signal, if real, lives exactly in the sparse
rows the census cannot certify. This story names the candidate; it cannot promote it.

## Deep-dive B — the 6 RESTORED_TO_EXPANSION

The rarest and most economically interesting branch: 6 of 69 reach shadow-resume EXPANSION.
Given SHADOW_PENDING, P(restore) = 1.0. All six, in full:

| TS | c | OHLC o/h/l/c | session | parent CRT | T1/T3 | mem/tb | ATR | age@restore | H20 | H40 | H60 | H80 | H100 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024-06-13 15:15 | 1457 | 2307/2308/2306/2308 | OFFHOURS_22_24 | RANGE_C1 | AGREE | SHORT/SHORT | 4.8 | 3 | +1.72 | +1.11 | +2.90 | +4.50 | +3.74 |
| 2024-06-25 17:45 | 2193 | 2325/2327/2324/2327 | ASIA_0_8 | RANGE_C1 | AGREE | LONG/SHORT | 1.3 | 4 | -3.64 | +0.82 | -5.04 | -8.44 | -9.10 |
| 2024-06-27 03:45 | 2321 | 2300/2300/2298/2299 | LONDON_8_13 | DISTRIBUTION_C3 | AGREE | LONG/SHORT | 3.0 | 3 | -6.88 | -5.63 | -6.06 | -6.29 | -1.31 |
| 2024-11-04 08:45 | 10785 | 2738/2742/2738/2741 | OVERLAP | MANIPULATION_C2 | DISAGREE | SHORT/LONG | 4.4 | 3 | +3.70 | +3.49 | +3.43 | +3.55 | +3.56 |
| 2025-06-03 16:15 | 24369 | 3360/3362/3358/3360 | OFFHOURS_22_24 | RANGE_C1 | AGREE | LONG/LONG | 2.8 | 3 | -5.60 | -8.87 | -8.97 | -11.17 | -8.77 |
| 2025-12-18 16:00 | 37377 | 4337/4341/4333/4336 | OFFHOURS_22_24 | RANGE_C1 | AGREE | LONG/LONG | 5.8 | 2 | -1.33 | -1.98 | -0.57 | -1.05 | -1.99 |

Observations (DESCRIPTIVE_ONLY):
- **3 of 6 restore on OFFHOURS** and 1 on ASIA (1457, 24369, 37377, 2193) — the low-liquidity
  hour cluster — yet those are the *weakest* earners (negative or small H20).
- The **only restore with DISAGREE T1/T3** (10785) — in the OVERLAP session, MANIPULATION_C2,
  pending_dir SHORT vs trend_bias LONG — is the single best economic event in the whole run:
  **H20 +3.70, and positive across every horizon H20→H100** (H40 +3.49 · H60 +3.43 · H80 +3.55 ·
  H100 +3.56).
- 4 of 6 restores had **mem LONG**; 4 of 6 resolve at **age 3** (1457, 2321, 10785, 24369).
- Restores are LONG-heavy (4/6), while **expires are SHORT-heavy (45: SHORT 30 / LONG 15)** — the
  direction skew from the prior notes holds.
- Aggregate restore H20 = **-2.0057** (n=6, INSUFFICIENT) — as a *class*, restores are not good
  economics on this object; the +3.7 is one exceptional kiss-of-life, not a restore rule.

## The End

Funnel tally, closing the run:

```
69 CREATE
├─ 45 EXPIRE (TTL)
├─ 17 CLEAR (non-HTF reset)
├─ 1  OVERWRITE
└─ 6  RESTORE → EXPANSION
```

Chapter totals (H20 memory_dir mean):
- **By fate:** CLEARED +1.6176 (n=14) · EXPIRED −0.4636 (n=45) · RESTORED −2.0057 (n=6)
- **By session:** OVERLAP +2.2483 (n=10) best · LONDON_8_13 +0.5368 · NY_17_22 −0.1377 · OFFHOURS
  −0.6658 · **ASIA_0_8 −1.5053 worst**
- **By parent CRT:** MANIPULATION_C2 +0.4492 (n=15) · RANGE_C1 −0.0760 · **DISTRIBUTION_C3 −2.2745**
- **By T1/T3:** DISAGREE +1.5017 (n=15) vs AGREE −0.6555 (n=50)

**Verdict (DESCRIPTIVE_ONLY, no promotion):** the economic signal this run *names* — not proves —
is the `t1_t3 = DISAGREE` create (n=15, H20 E=+1.50) sharpened by **London-NY overlap** session and
embodied most purely in candle **10785** (the only DISAGREE restore, H20 +3.70, positive at every
horizon). The anti-signal chapters are **ASIA hours** (−1.51), **DISTRIBUTION_C3** (−2.27), and the
plain **AGREE / RANGE / SHORT-expire majority**. Every positive cell is power-INSUFFICIENT (n<30);
nothing promotes.

`economic_claims_allowed = false` · authority: none · no continuous_disp flip · no CHoCH · no
occupancy reopen · no parity optimize · no economic promotion · no TTL flip.

**JSON:** `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/story_rows.json`
**Full census:** `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/census.json`
**Source objects:** `run_20260906_013609` (dual-construction) · corpus sha `4d73f5ce…` · cost SEM-015