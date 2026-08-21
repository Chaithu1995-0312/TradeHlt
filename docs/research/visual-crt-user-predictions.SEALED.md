# Visual CRT User Predictions — SEALED

Experiment: CH-visual-crt-state-fidelity
Date (UTC): 2026-08-18
Status: SEALED
Prediction basis: pre-registration, before any visual item was generated or any label was observed.

These are the assistant/researcher predictions for the pre-registered visual CRT state-fidelity experiment. They are recorded before item generation and before any label is observed.

| Cell | Prediction |
|---|---|
| V1 Arm 1 (bare) | κ ∈ [0.15, 0.35] |
| V1 Arm 2 (level drawn) | κ ≥ 0.65 |
| V1 Arm 2 − Arm 1 | ≥ +0.30 |
| V2 DISPLACEMENT | INSUFFICIENT at n=19 |
| V3 EXPANSION | INSUFFICIENT by construction at n=6 |
| V4 RETEST | INSUFFICIENT by construction at n=2 |
| Controls, Arm 1 | observer-positive ≥ 20% |
| LLM-vs-human ceiling | κ ≥ 0.55 |

## Interpretation predictions

- V1 Arm 2 substantially higher than Arm 1, with Arm 2 − Arm 1 ≥ +0.30: the engine's sweep classification is visually faithful when its reference level is made visible; disagreement in the bare arm is primarily attributable to level visibility/choice, not necessarily state logic.
- V1 Arm 2 also low: the state logic may diverge from what an observer sees even when the engine's reference level is supplied; this is the branch that warrants semantic review.
- High observer-positive rate on controls: evidence about possible engine coverage/missed chart-visible events, not evidence that the engine is incorrect.
- Visual-question ceiling below 0.5: the question is too ambiguous for a reliable engine conclusion.
- Any cell with fewer than 15 minority-class instances is INSUFFICIENT, never a null result.

## Scope

These are predictions only. They do not assert any observed result, engine defect, semantic conclusion, economic edge, or production authority.

The prediction file must remain sealed until scoring is complete. After scoring, the SHA-256 of this exact file is to be compared with the preregistered hash before the file is opened for interpretation.

SEALED
