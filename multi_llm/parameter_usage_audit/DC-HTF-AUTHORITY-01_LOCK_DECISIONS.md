# DC-HTF-AUTHORITY-01 — Lock decisions audit

**Purpose:** Record every option presented and which one User froze (D1–D3).  
**Does not authorize** patch apply. W1 counterfactual HARD GATE still open.

Updated: 2026-09-22T04:26:16Z (UTC) / 2026-09-22 IST

## Policy bundle (frozen)

| Lock | Chosen | Formula |
|---|---|---|
| **D1** DIR | **REPLACE_CLOCK × SYMMETRIC** | break := (close > h_ref) ∨ (close < l_ref); clock_flip ∉ reset_causes |
| **D2** PROT | **KEEP baseline** | suppressed ∈ {EXPANSION, RETEST, OPEN, TP1} |
| **D3** ORD | **BREAK_ONLY** | eval_order := [structural_break]; clock never resets |

## D1 — options presented → choice

| Option id | Label | Recommended | **Chosen** |
|---|---|---|---|
| REPLACE_SYMMETRIC | REPLACE × SYMMETRIC | yes | **YES** |
| REPLACE_DIRECTIONAL | REPLACE × DIRECTIONAL | no | no |
| ADD_SYMMETRIC | ADD × SYMMETRIC | no | no |
| ADD_DIRECTIONAL | ADD × DIRECTIONAL | no | no |

Source answer: `D1: REPLACE_CLOCK × SYMMETRIC`

## D2 — options presented → choice

| Option id | Label | Recommended | **Chosen** |
|---|---|---|---|
| KEEP | KEEP baseline (EXPANSION / RETEST / OPEN / TP1) | yes | **YES** |
| EXTEND | EXTEND (baseline + named extras) | no | no |
| DROP | DROP protects for structural break | no | no |

Source answer: `D2: KEEP baseline EXPANSION / RETEST / OPEN / TP1`

## D3 — options presented → choice

| Option id | Label | Recommended | **Chosen** |
|---|---|---|---|
| BREAK_ONLY | BREAK_ONLY | yes | **YES** |
| BREAK_THEN_CLOCK | BREAK_THEN_CLOCK | no | no |
| CLOCK_THEN_BREAK | CLOCK_THEN_BREAK | no | no |
| CLOCK_ONLY | CLOCK_ONLY | no | no |

Source answer: `D3: BREAK_ONLY`

## Still open

| Gate | Status |
|---|---|
| W1 counterfactual (fate of 1442 RESET_HTF) | NOT STARTED — HARD GATE |
| Structural-break patch | PARKED |
