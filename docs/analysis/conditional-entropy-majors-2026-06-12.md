# Conditional-entropy map — where does next-direction become predictable on the crypto majors?

> **Point-in-time analysis (history, not living truth).** Date: 2026-06-12 · Branch: `patch` ·
> Phase B (B1). Measure-only, **candle-only** (no CRT/spine labels). Artifact:
> `results/research/phase_b/phase_b_conditional_entropy.json` (deterministic; run1≡run2 SHA
> `226481F2…`). Driver: `scripts/research/phase_b_conditional_entropy.py`; core:
> `src/research/conditional_entropy_grid.py`. Conclusion promoted to the living record as **F-020**.

## Why this run

Phase A (F-019) found **no *global* edge** on the crypto majors. Phase B asks the different
question: **where, if anywhere, does *local* directional information emerge?** Design (chosen this
session): **paired — entropy PRIMARY, economics CONFIRMS survivors**; significance on the
**PARTITION** (`session × vol-tercile × momentum-regime`), not the cell; two separate BH families
(A = per-instrument 4×5=20 tests; B = pooled 5 tests); horizons `{1,3,5,10,20}`; intrabar_fixed +
12 bps. CRT-event labels deferred to B2 to avoid rediscovering the spine.

## Result — `VERDICT: ENTROPY_LEAD_NO_ECON`

| | Family A (per-instrument) | Family B (pooled) |
|---|---|---|
| Partitions BH-significant | **20 / 20** | **5 / 5** |
| Permutation p | all at the **0.0020 floor** (1/501) | all at 0.0020 |
| Information gain `IG` | **0.0011 – 0.0036 bits** | 0.0012 – 0.0018 bits |
| `H(dir \| partition)` | **0.995 – 0.999** (≈ coin-flip) | 0.998 – 0.999 |
| `p_up` | 0.50 – 0.52 | 0.51 |
| Stage-3 candidate cells | **74** | (per-instrument only) |
| **Economic pockets (clear BOTH)** | **0** | **0** |

Sanity anchor: BNBUSDT@1 `H_uncond = H_cond + IG = 0.9981 + 0.00138 ≈ 0.9995` reproduces the
`process_diagnostics` global ≈0.999.

## What this means

1. **Every partition is "statistically significant" — and that fact is meaningless here.** At
   N≈70k (per-instrument) to ≈280k (pooled), the observed information gain (however microscopic)
   always exceeds all 500 random-partition shuffles, so the permutation test saturates at its
   floor for **all 25 partitions**. This is the textbook **"significant ≠ exploitable"** regime the
   process-characterizer flagged (tiny ρ/MI trip flags at large N). Partition significance is
   **necessary-but-not-sufficient**; the real signal is the *effect size* — and `IG ≈ 0.002 bits`
   (≈0.2% of one bit) with `|p_up − 0.5| ≈ 0.01–0.02` is **economically negligible**.

2. **The paired design did its job — it caught the false lead.** The entropy axis *alone* would
   have reported "20/20 significant partitions" and sent us chasing ghosts. The **economic second
   stage filtered all 74 candidate cells to ZERO pockets**: no cell clears both a BH-significant
   sign-following expectancy AND `|ΔE| > 0.05R` under intrabar_fixed + 12 bps. Requiring **both**
   is exactly what prevents "significant but unexploitable" (entropy-only) and "profitable by luck"
   (economics-only).

3. **The direction null is now CONDITIONAL too.** No candle-derivable conditioning
   (`session × vol × momentum`, horizons 1–20, per-instrument or pooled) yields an exploitable
   directional pocket on crypto-major M15. This **extends F-001/F-002/F-019 from "no global edge"
   to "no local edge in the candle-conditional grid."** It also corroborates the earlier
   BNBUSDT-only economic conditional study (`bnbusdt-conditional-edge-2026-06-10.md`, no pockets in
   130 buckets) on the new information axis and across all four majors.

## Roadmap implication

- **B1 is terminal for next-direction.** The gate for advancing was a genuine lead = *entropy
  pocket **and** economic pocket*. We have entropy "significance" everywhere but **zero economic
  pockets**, i.e. no genuine lead. **B2 (CRT-event labels) is therefore NOT entered** — harvesting
  spine telemetry would only add complexity over a null.
- **Redirect off next-bar direction.** The accumulated evidence (F-019 + F-020) says directional
  *entry* prediction is not the lever on crypto-major M15. The remaining live threads are
  **non-directional**: the spine's *selection/throughput* (the SOL n=7 / F-015 pooling lead from
  Phase A) and **exit/cost structure** (the 88%-plain_stop_loss + cost-drag forensics) — neither of
  which is an entry-direction problem.

## Method note (kept for replay)

Partition-level permutation significance saturates at this N and is not, by itself, a useful
discriminator — future conditional studies should read the **effect size + economic stage**, not
the significance flag. The grid knobs (horizons, session windows, momentum ε, floors,
permutation counts) live in `configs/research/research_config_phase_b.json` (no magic numbers).

## Reproduce
```
python scripts/research/phase_b_conditional_entropy.py
```
Deterministic: JSON body carries no wall-clock; a second run is byte-identical (`226481F2…`).
