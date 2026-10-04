# T4 — Measurement contract (Sense B)

## Walk result (2026-08-15)

**Verdict: INSUFFICIENT.** Not an edge. Not a kill. Not admissible.

| Item | Value |
|---|---|
| Contract | `MC-CRT-SB-XAUUSD-M15-V1` |
| Corpus | `data/mt5/XAUUSD_M15.csv` (47,275 bars, 2024-05-22 → 2026-05-21) |
| Clock declared | `MT5_SERVER_NY_DST` (F-066; not UTC) |
| Gate | ON — `EngineRunner.run` called **3** times (non-vacuous) |
| `TRADE_OPENED` n | **3** (need ≥ 30) |
| OOS n | 1 |
| `economic_claims_allowed` | **false** |
| mt00 / mt01 | still **UNRUN** (this was a diagnostic walk) |

Artifacts: `results/research/mc_crt_sb_xauusd_m15_v1/`

## Why numbers must not be quoted as an edge

1. n=3 < 30 → INSUFFICIENT (contract kill/insufficient rule).
2. Re-derive sign agreement vs spine ledger = **0.67** < 0.99 → `BLOCK_EXPERIMENT` (spine scale-out vs single-TP2 walk + 12 bps on tiny stops).
3. 12 bps of gold price vs ~1–4 point stops produces cost of **0.7–3.3 R** per trade. Uncalibrated. The one TP2 still nets negative under that cost.

Descriptive only: 3 longs; 2 SL in 1 bar; 1 TP2 that is net-negative after 12 bps.

## Still not done

E-MT-00 probes, E-MT-01 0/27, CRT CLOSED, production control, a found edge.

## SOFF walk — new object (2026-08-15)

**Contract:** `MC-CRT-SB-XAUUSD-M15-SOFF-V1` (new id, not a V1 tweak).  
**Object:** CRT `allowed_sessions` = all windows + `OFF_SESSION`, in-process only. Production JSON not written.

| | V1 prod sessions | SOFF |
|---|---:|---:|
| n TRADE_OPENED | 3 | 12 |
| EngineRunner calls | 3 | 16 |
| Verdict | INSUFFICIENT | INSUFFICIENT |

Adapter still rejected 4 as `invalid_session`. Session was a bind, not the only bind. n=12 still < 30. No edge. Artifacts: `results/research/mc_crt_sb_xauusd_m15_soff_v1/`.

## NS walk — third object (2026-08-15)

**Contract:** `MC-CRT-SB-XAUUSD-M15-NS-V1`  
CRT all-sessions **and** adapter `allowed_sessions` includes asia/overlap/closed. In-process only.

| | V1 | SOFF | NS |
|---|---:|---:|---:|
| TRADE_OPENED | 3 | 12 | **16** |
| EngineRunner calls | 3 | 16 | **16** |
| Verdict | INSUFFICIENT | INSUFFICIENT | **INSUFFICIENT** |

Adapter session veto is gone (16=16). Still n=16 < 30. Remainder: inverted SL, Ultron, CRT funnel. No edge. Artifacts: `results/research/mc_crt_sb_xauusd_m15_ns_v1/`.
