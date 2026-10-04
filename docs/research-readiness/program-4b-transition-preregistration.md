# Program 4b — Non-Directional Target: Regime TRANSITION Forecast (forward Markov P^H) · PRE-REGISTRATION

> **Program 4b tests whether *anticipating a volatility-regime change* — not the current regime
> level — can be converted into money inside a spot directional architecture. It is a different
> information channel from Program 4 (which tested the level and was KILLED, F-030), not a reopen of
> it.**

Status: **PRE-REGISTERED — design frozen, NOT yet built/run** · Date: 2026-06-17 · Branch: `patch`
Parent: Program 4 (level channel, KILLED — F-030). Governance: inherits Program 4 verbatim.

---

## 1. Why this is a NEW ontology, not a reopen

Program 4 conditioned consumers on the **contemporaneous regime level** {C,N,E} and found it
economically non-consumable on the powered toys (F-030: statistically informative, `p≈0.0025`, but
the best regime's expectancy never crosses 0; 2 cells pure persistence). That result is *conclusive
for the level channel* — under `H_atr=0.885` the current regime is the best-case level predictor, so
a noisier forecast cannot rescue level conditioning.

But a contemporaneous label **cannot express "a transition is coming."** Anticipating a regime
*change* (e.g. compression→expansion before a breakout) is a **different information channel** — the
one `expansion_breakout` would most plausibly exploit. Program 4 never tested it (the shipped labeler
omitted the promised Markov step). Per the anti-archaeology rule, a different channel = a different
ontology = a separate pre-registration. **This is not "Program 4 with a bigger window."**

---

## 2. The forecast mechanism (the only genuinely new code)

A **forward Markov `P^H` projection**, fully no-lookahead, added to `regime_observer.py`:

- States `S_t ∈ {C,N,E}` from the SAME trailing-window vol terciles as Program 4 (reused verbatim).
- Trailing transition matrix `P_t(i,j)` estimated over a pre-committed window `W_markov`, counting
  **only completed transitions `τ → τ+1` with `τ+1 ≤ t`** (rows with no occurrences → uniform `1/3`).
- `H`-step projection `f_{t+H} = v_t · P_t^H` (`v_t` = one-hot current state); forecast regime
  `Ŝ_{t+H} = argmax f_{t+H}`, confidence `γ = max f_{t+H}`.
- Conditioning partitions a consumer's outcomes by **`Ŝ_{t+H}` at the entry bar** (the *predicted*
  regime), not the current one. Everything downstream (forward_walk, EdgeAggregator,
  QualificationGate, the cross-matrix, BH) is reused UNCHANGED.

**No-lookahead is load-bearing:** `P_t` counts only transitions completed at or before `t`; extend
the `test_no_global_rank_leak` truncation test to assert `Ŝ_{t+H}` at index `k` is invariant to any
data appended after `k`.

---

## 3. Hardenings adopted from the 2026-06-17 review (pre-committed)

1. **Hard calibration gate** — the CLI **raises** if BNBUSDT `H_atr ∉ 0.885 ± 0.03` (Program 4's was
   advisory). No economic claim runs on an instrument whose vol-memory prior isn't reproduced.
2. **`lag_k = forecast horizon H`** (explicit) — the lagged-regime control uses `Ŝ` computed at
   `t−H`, so it directly tests whether the *forward* forecast beats a naive same-horizon-stale one.
3. **5th control — within-tercile shuffle** — shuffle regime labels *within each vol-tercile bucket*,
   destroying transition dynamics while preserving the vol level. Isolates "transition information"
   from "level information": if the within-tercile-shuffle reproduces the uplift, the edge is level
   (already falsified, F-030), not transition.

Controls a–d from Program 4 carry over (random, shuffled, unconditioned-baseline, lagged).

---

## 4. Verdict classes (unchanged from Program 4 v1.2)

`REGIME_EXPLOITABLE` (the only result that unlocks Stage 4 Truth-Half-Life) · `REGIME_INFORMATIONAL`
· `REGIME_HARMFUL` · `REGIME_REDUNDANT` · `REGIME_INSUFFICIENT` (underpowered, e.g. the spine arm —
no claim). Significance via the label-permutation null of `S = max_g (cell_E − uncond_E)`; `EXPLOITABLE`
requires clearing M4 + beating all five controls + the within-tercile-shuffle.

---

## 5. Fixed, pre-committed parameters (anti-archaeology)

FROZEN for the single pass — changing any after a null is forbidden archaeology:

| Parameter | Value | Notes |
|---|---|---|
| `atr_period` | 14 | reused from Program 4 |
| `tercile_window` | 480 | reused from Program 4 (trailing-only) |
| `W_markov` | 480 | transition-count window (trailing, completed transitions only) |
| `H` (forecast horizon) | 8 bars | the projection horizon `P_t^H`; `lag_k = H = 8` |
| `min_cell_samples` | 30 | mirrors `q_min_samples`; all-underpowered consumer → INSUFFICIENT |
| `harmful_margin` / `redundant_tol` | 0.05 R | as Program 4 |
| `null_relabelings` | 200 | label-permutation null |

**One shot.** If the single pass fails its controls → STOP. No `W_markov`/`H`/tercile grid, no extra
consumers, no "just one more." First falsification carries authority. Reopen only via yet another new
ontology (non-spot execution / optionality / a non-crypto universe), NOT a parameter pass.

---

## 6. Calibration gate (hard — runs before any economic claim)

On BNBUSDT, `process_characterization` must report `volatility_persistent` and `H_atr ∈ 0.885±0.03`;
otherwise the CLI raises and the economic verdict is void (instrument/labeler invalid).

---

## 7. Verdict-binding

The result is registered as a finding (**F-031**, reserved) the same turn it is produced; on a null,
Program 4b is KILLED/FROZEN in the Funding Ledger with new-ontology-only reopen conditions, per
CLAUDE.md §6.2. The §5 fixed params are named forbidden reopen routes.

---

## 8. Build checklist (a future session — NOT done here)

1. `regime_observer.py`: add `MarkovRegimeForecaster` (trailing `P_t`, `P_t^H`, `argmax`/confidence);
   keep the existing `RegimeLabeler` (level) intact.
2. CLI: hard calibration gate; `lag_k=H`; wire the predicted-regime partition.
3. `regime_conditioning.py`: add the within-tercile-shuffle control.
4. Tests: extend no-lookahead truncation to the forecast; determinism; within-tercile-shuffle control.
5. Run once across crypto majors → register F-031 with the verdict the same turn.
