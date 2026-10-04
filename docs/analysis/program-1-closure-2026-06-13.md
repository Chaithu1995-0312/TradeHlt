# Program 1 Closure — Next-Bar Directional Ontology (M15 crypto majors, intrabar_fixed + 12bps)

> **Point-in-time closure record (history, not living truth).** Created: 2026-06-13 · Branch: `patch`.
> Program 1 is **research-complete / KILLED** (see `docs/current-findings.md` § Funding Ledger). This
> doc is the durable synthesis; the living authority is the four findings + the ledger entry.

## What Program 1 was

The search for a **profitable next-bar directional edge** on **crypto-major M15** (BNB/ETH/BTC/SOL,
plus XRP/DOGE where data allowed), measured under one fixed **governing truth standard**:
**intrabar_fixed exits + 12bps round-trip cost, per-instrument + pooled, in-sample + 70/30 OOS**, with
falsification controls and multiple-comparison correction. The program swept the decision pipeline end
to end: **entry → conditional direction → selection → exit**.

## The four-falsification sweep — all null

| Branch | Finding | What was tested | Verdict | Evidence (deterministic JSON) |
|---|---|---|---|---|
| Entry edge | **F-019** | Existing hypothesis pool through the M4 7-gate qualification across the majors | **null** — zero PROMOTE; toys ≈ random; spine throughput-starved | `results/research/qualification/qualify_majors.json` (`2ccc3e98…`) |
| Conditional direction | **F-020** | H(next-dir \| session×vol×momentum), horizons 1–20, entropy **paired** with economics | **null** — 25/25 partitions "significant" at N but IG≈0.002 bits; 0 economic pockets | `results/research/phase_b/phase_b_conditional_entropy.json` (`226481F2…`) |
| Selection skill | **F-021** | RETEST selected−rejected ΔE, pooled-by-effect, **decomposed by reject-reason** | **null** — the entire +1.17R effect IS the (F-017-null) SESSION filter; ZONE 0 rejects, SCORE noise | `results/research/phase_s/phase_s_selection_effect.json` (`DA252DC6…`) |
| Exit/cost geometry | **F-025** | 42-cell SL{0.5–3.0}×TP{1.0–5.0} grid, entries fixed | **null** — every cell E_oos<0; max recoverable +0.30R = cost recovery, still negative | `results/research/phase_d/phase_d_exit_grid.json` (`6C4D537A…`) |

All four answered **null** under the same standard. No learnable next-bar directional edge exists in
this ontology on crypto-major M15 under realistic exits.

## The real achievement — the guards that fired (transferable asset)

Every branch produced a **headline that looked like an edge**, and in every branch a **decomposition
guard killed the false positive**. This machinery is more valuable than any single experiment, because
it is the part that generalizes to Program 2:

- **F-020 — entropy-significance saturation → killed by economics.** At N≈70k every partition trips
  the permutation floor ("25/25 significant"), which would have looked spectacular. The **paired
  economic stage** found **0 exploitable pockets** (IG≈0.002 bits is economically meaningless). *Lesson:
  statistical significance ≠ economic value at large N; pair information with economics.*
- **F-021 — a +1.17R selection "edge" → killed by reject-reason decomposition.** Selected retests beat
  rejected by +1.17R, p<0.001, OOS +1.21, 4/4 — a spectacular headline. Decomposing by reject-reason
  localized **100% of it to the SESSION class** (≡ ALL), which F-017 already proved non-improvable; the
  genuine skill classes (ZONE/SCORE) were empty/noise. *Lesson: decompose an aggregate before believing
  it; an "edge" is often a relabeled, already-falsified lever.*
- **F-025 — a positive grid cell + spine ALPHA banner → killed by ceiling/regime + strict OOS +
  sample-size.** The spine arm fired an ALPHA regime banner and nominal leads — but the **ceiling gate**
  (structural ≤0 → ENGINEERING) framed the universe arm correctly, and the **strict E>0-IS-AND-OOS bar +
  N-scrutiny** demoted the spine "lead" to a tiny-N artifact (n=30, 2/4 instruments, ~9 OOS trades).
  *Lesson: compute the ceiling before ranking; never read a cell before the regime; n=30 is not an edge.*

The **planted-edge harness-validity tests** (a real edge *must* surface) make each null **trustworthy**,
and **D4 was deliberately not entered** on the non-credible spine lead — the discipline that prevents the
optimization spiral.

## The decisive number — the reality gap

Phase D's D1 ceilings quantified *where the missing value lives*:

```
structural_upper_bound       (attainable best fixed exit)  ≈ −0.175 R
perfect_information_upper_bound (unattainable foresight)    ≈ +3.98  R
reality_gap                                                ≈ +4.16  R   (≈104% of value)
ceiling_utilization                                        ≈ −4%
loss: plain_stop_loss 90.55% · same_bar 9.25% · cost_drag 0.05%
```

**Even perfect exits cannot recover what is missing.** The favorable excursions exist, but gross E≈0
means you cannot know *which* trades will move — so no fixed exit captures them. The value is **upstream
and informational, not downstream geometry.** Exits improve **risk** (MaxDD via wider stops), not
**expectancy.** That is the whole program in one number.

## EXHAUSTED ≠ WRONG — what was falsified vs the untouched frontier

Program 1 falsified a **specific ontology**, not "markets are random." What is closed:
**next-bar direction · M15 · crypto-majors · these entry families · directional-target**.

What remains **untouched** (candidate **Program-2** ontologies — *recorded, deliberately deferred; a
fresh program decision, NOT a continuation of Program 1*):

| Axis | Untouched alternatives |
|---|---|
| **Target** | volatility · range expansion · persistence (not direction) |
| **Horizon** | H1 · H4 · daily (not next-bar M15) |
| **Asset class** | FX · equities · commodities (not crypto-majors) |
| **Objective** | market-making · carry · relative-value · dispersion (not directional speculation) |
| **Labels** | event-conditioned states · structural regimes (not candle-derived partitions) |

Each is a **new program** with its own pre-registered hypothesis and the same governing-truth discipline.
None is implied to contain edge; none is started here.

## What must NOT be done (encoded in the KILLED reopen conditions)

Program 1 is **not reopenable by any parameter pass.** The following are **archaeology**, explicitly
out of bounds: more SL/TP grids · more TP ratios · trailing-stop variants · more entropy partitions ·
more score thresholds · more session sweeps · re-running any of F-019/020/021/025 with tweaked knobs.
Reopening requires a **genuinely new ontology** (a Program-2 decision), not optimization.

## Frozen artifacts (deterministic, regenerate-don't-edit)

| Phase | Driver | Result JSON | Body SHA-256 |
|---|---|---|---|
| Entry (F-019) | `scripts/research/qualify_majors.py` | `results/research/qualification/qualify_majors.json` | `2ccc3e98…` |
| Conditional (F-020) | `scripts/research/phase_b_conditional_entropy.py` | `results/research/phase_b/phase_b_conditional_entropy.json` | `226481F2…` |
| Selection (F-021) | `scripts/research/phase_s_selection_effect.py` | `results/research/phase_s/phase_s_selection_effect.json` | `DA252DC6…` |
| Exit (F-025) | `scripts/research/phase_d_exit_grid.py` | `results/research/phase_d/phase_d_exit_grid.json` | `6C4D537A…` |

Each driver is deterministic (proven by a byte-identical re-run) and reuses the audited research truth
standard (`forward_walk` intrabar_fixed + `CostModel` 12bps). Engineering value that *does* survive —
wider stops reduce `cost_r` and MaxDD at flat-negative E — is **portfolio/risk hygiene, not alpha**, and
is recorded only as such.
