# Exit/cost grid — maximum recoverable expectancy from post-entry geometry (crypto-6)

> **Point-in-time analysis (history, not living truth).** Date: 2026-06-13 · Branch: `patch` ·
> Phase D (D1+D2). Measure-only. Artifact: `results/research/phase_d/phase_d_exit_grid.json`
> (deterministic). Driver: `scripts/research/phase_d_exit_grid.py`; core: `src/research/exit_grid.py`.
> Conclusion promoted to the living record as **F-025**.

## Why this run

After F-019 (global direction), F-020 (conditional direction) and F-021 (selection-beyond-session),
**exit/cost was the last unfalsified branch**. But the forensics show **gross E ≈ 0**, so the question
was bounded: *what is the maximum recoverable expectancy attributable purely to post-entry geometry,
holding entries fixed?* — with a **strict bar: success = E>0 IS AND OOS** (everything else =
risk/cost engineering, not alpha). Two populations: the **toy universe** (n=53,629 → power) and the
**spine's executed trades** (n=30 → relevance). A 42-cell SL{0.5…3.0}×TP{1.0…5.0} grid, intrabar+12bps,
IS+OOS. D1 reports the recoverable-value ceilings and a REGIME banner *before* any cell is read.

## Result

### UNIVERSE (n=53,629) — decisive · `REGIME: ENGINEERING` · **NO LEAD**
| Ceiling | Value |
|---|---|
| structural_upper_bound | **−0.175 R** (≤0 → ENGINEERING) |
| perfect_information_upper_bound | +3.983 R |
| **reality_gap** | **+4.158 R** |
| ceiling_utilization | **−4%** → *value lost to entries: 104%, to exits: −4%* |

Decomposition: `E_gross −0.049` (≈0), `E_net −0.427`, `cost_drag 0.379`. Loss mechanisms:
**plain_stop_loss 90.55%**, same_bar_conflict 9.25%, timeout 0.15%, cost_drag 0.05% — the BNB
forensic (`bnbusdt-forensics-2026-06-10.md`) now confirmed **cross-instrument**.

Grid (all 42 cells `E_oos < 0`): incumbent (1.0,2.0) **−0.569**; best (3.0,5.0) **−0.271**;
`max_recoverable_E = +0.299` (the cost-recovery gradient — wider stops lower cost_r: 0.5×5.0 = −0.840
→ 3.0×5.0 = −0.271 — but **never positive**). **No cell clears the strict bar.**

### SPINE (n=30: BNB 13/BTC 5/ETH 5/SOL 7) — relevance · `REGIME: ALPHA` · nominal LEAD (artifact)
The spine's 30 entries are gross-positive under a 1:2 geometry (`E_gross +0.5`), so structural =
+0.39 → ALPHA. The mechanical bar flags leads at wide-TP cells:

| Cell | E_IS | E_OOS | sign | MaxDD(R) |
|---|---:|---:|:--:|---:|
| 0.75×4.0 | +0.865 | +0.327 | **2/4** | 4.6 |
| 0.75×5.0 | +1.109 | +0.293 | **2/4** | 5.0 |
| 1.0×5.0 | +1.076 | +0.048 | **2/4** | 4.0 |
| 1.0×2.0 (incumbent) | +0.387 | −0.355 | 1/4 | 2.3 |

**These are a tiny-N artifact, NOT an edge:** n=30 → ~9 OOS trades pooled; sign-consistency is **2/4
instruments** (a coin-flip split, the boundary of the ≥-majority rule); the wide-TP cells are
dominated by 1–2 outliers on ~9 trades. The decisive universe arm (n=53k) is unambiguously
ENGINEERING/no-lead, and gross E≈0 forbids real exit alpha. Per doctrine the spine lead is a
**PRE-REGISTERED OOS CANDIDATE, never an edge** — and untestable without more spine throughput
(F-015-exhausted). **D4 is deliberately NOT entered** (early-invalidation/trailing on n=30 is the
optimization spiral the gate exists to prevent).

## What this means

1. **Fourth falsification (on the powered evidence).** No SL/TP geometry recovers positive OOS
   expectancy on the universe. `max_recoverable_E = +0.30R` is **cost recovery via wider stops**, and
   it lands at −0.27R — still net-negative. **Exits are a risk/cost-management lever, not an
   expectancy lever** — confirming F-002 ("structure SL/TP is risk-shaping, not alpha") cross-instrument
   under the governing intrabar standard.

2. **The bottleneck is ENTRY INFORMATION, quantified.** `reality_gap = +4.16R` with `ceiling_utilization
   = −4%`: the favorable excursions exist (perfect-foresight ceiling +3.98R) but are uncapturable by
   any fixed exit because gross E≈0 means you cannot know *which* trades will move. ~104% of the
   missing value is attributable to entries, not exits. The `plain_stop_loss 90.55%` share is an
   entry-information problem, not an exit problem.

3. **The ceiling gate + regime banner did their job.** Printing `REGIME: ENGINEERING` and the ceilings
   above the grid meant the +0.30R cost-recovery and the lower-MaxDD wide-stop cells are read as
   engineering, never alpha. And the spine arm's ALPHA banner correctly surfaced *because* its 30
   entries are gross-positive under 1:2 — then the strict bar + N-scrutiny correctly demoted the
   "lead" to a tiny-N artifact. Interpretation preceded observation, as designed.

## Roadmap implication — the first full research-program sweep is closed

Every branch of the current system is now measured **null under the governing intrabar+12bps standard**:

| Branch | Finding | Verdict |
|---|---|---|
| Global direction | F-019 | null |
| Conditional direction | F-020 | null |
| Selection (beyond session) | F-021 | null |
| Exit/cost geometry | **F-025** | null (risk/cost lever only) |

The open question is no longer "**which lever?**" but, per the reality_gap, "**is the ontology wrong?**"
— next-bar direction on this entry family may simply be the wrong variable. That is a deeper redirect
(new instrument class / timeframe / target definition) than any further parameter search, and it is
**not** another grid. Engineering value remains available (wider stops cut cost_r and MaxDD at flat
negative E), but that is portfolio/risk hygiene, not alpha.

## Reproduce
```
python scripts/research/phase_d_exit_grid.py
```
Deterministic: JSON body carries no wall-clock; a second run is byte-identical.
