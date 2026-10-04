# Context attribution beyond CRT state — XAUUSD M15 holdout

**Contract:** `MC-CTXATTR-XAUUSD-M15-V1` · **Ontology:** SEM-035 / SEM-036 ·
**Change:** `CH-v3-unified-market-structure-v1` · **Date:** 2026-08-29 ·
**Finding:** F-097

Point-in-time analysis. Not a living doc. Research authority only —
`economic_claims_allowed` is false and mt01 is 0/27, so the E4 seal is unmet regardless of what
follows.

---

## The question, and why it had to be asked sideways

"Which context features improve expectancy beyond CRT alone?" cannot be asked of CRT's own
trade ledger. On the current HEAD, a full XAUUSD M15 backtest produces **3 trades across 47,275
bars** (`total_setups: 3`). Eleven context families against n=3 is not an underpowered study; it
is not a study. That is the same wall that closed F-026 at n=47 and F-094 at n=9.

So the population was inverted, as F-086 did: **every bar × both directions**, labelled at
source by `multi_tp_walk` (SEM-017) under the production two-target geometry, net of the
measured XAUUSD broker cost (SEM-015) with adverse stop fills (SEM-016). The CRT state is not
discarded — it becomes the **stratum**.

**This measures the every-bar population, not production's executed trades.** That sentence is
in the contract's `authority.note`, and it is the single most important limit on everything
below.

---

## Method

| | |
|---|---|
| Units | 94,314 (bar × direction), PRIMARY label arm `disp_bar` / `production` |
| Train / holdout | 75,302 / 18,830, embargo 182 dropped |
| Holdout start | 2025-12-24 19:15:00 (corpus index 37,820) — the frozen MC-ASYM calendar, shared with MAGPRIOR / MRPRIOR / VCRTPRIOR |
| Families | 11 (10 single + 1 composite) × 2 directions = **22 pre-registered tests** |
| Primary metric | `delta_within_stratum` — mean-preserving overlay (`w = 1 ± 0.5`) on **stratum-centered** y, inside each `crt_state_after`, aggregated size-weighted |
| Multiplicity | BH-FDR q=0.10 over 22, p from block permutation (block 40 bars, 199 perms), plus train/holdout sign match, plus a pass-count ceiling of 6 |
| Controls | `long_only` (binding), `random_entry`, and a shuffled-context null permuted **within** stratum |

### Why the metric is centered

The raw overlay delta is `k · (n_a·mean_a − n_d·mean_d) / n`. If the context carries no
information at all (`mean_a == mean_d == m`), that reduces to `k · m · (n_a − n_d) / n` —
**non-zero whenever the cells are unbalanced and the stratum mean is not zero.** The stratum
means here run to −0.29R, so an information-free context with a lopsided agree/disagree split
would have scored a spurious effect of roughly the size the program was looking for.

Centering y on its own stratum mean removes exactly that term. Strata where the context does
not vary at all are skipped, because a uniform `1+k` rescale is not a contrast.

Both corrections were made **before any outcome was computed**, caught by the orthogonality
floor while it was still a planted-fixture test, and the amendment is recorded in the
contract's `authority.note`.

---

## Result: 0 of 22

**`NO_FAMILY_CLEARS`.** And it is a **powered** null, not an insufficient one:

| Gate clause | Cells passing |
|---|---|
| Powered (holdout agree ≥30 **and** disagree ≥30) | **22 / 22** |
| Train/holdout sign match | 16 / 22 |
| Survives BH-FDR at q=0.10 | **0 / 22** |
| Beats `long_only` **and** shuffled-context | **0 / 22** |

Holdout cells run from 192 to 5,142 per side — hundreds to thousands, not tens.

### The binding constraint is the passive control, again

`long_only` holdout mean = **−0.1731R** (train −0.2935R, which reproduces F-086's ≈−0.29R base
rate). Every observed `|delta_within_stratum|` falls in **0.002 – 0.064**. The largest effect
in the entire matrix is 2.7× smaller than the control it has to beat.

This is F-086's mechanism repeating: XAUUSD rose across this corpus, so **zero is the wrong
reference**. Measured against zero, 16 of 22 cells look "positive". Measured against passive
same-direction exposure, none of them survive.

### Significance does not rescue it either

The smallest p in the matrix is **0.015** (`order_block|long` and `choch|long`). The BH-FDR
threshold for rank 1 of 22 at q=0.10 is **0.00455**. Neither is close, and both would still have
had to clear the controls afterwards.

---

## The diagnostic that earned the program its keep

`crt_proxy_component = delta_marginal − delta_within_stratum` measures how much of a naive
reading was really CRT state wearing the family's name. It is large, and for one family it is
larger than the effect:

| Cell | marginal | within-stratum | proxy component |
|---|---:|---:|---:|
| `htf\|short` | +0.0756 | +0.0117 | **+0.0639** (85% of it) |
| `htf\|long` | +0.0247 | **−0.0207** | **+0.0454** |
| `objective\|long` | +0.0633 | +0.0192 | +0.0441 |
| `objective\|short` | +0.0476 | +0.0157 | +0.0319 |

`htf|long` is the sharpest case: naively, HTF agreement looks **+0.0247 helpful**; conditioned on
CRT state it is **−0.0207**, an outright sign flip. The whole apparent effect was the CRT state,
and then some.

That is mechanically sensible — HTFState and ObjectiveStatus are parent-timeframe context that
co-moves with CRT phase by construction — but it is exactly the confound that an uncontrolled
version of this study would have reported as a discovery.

---

## Scope and limits

- **Every-bar population, not production trades.** Nothing here says what would happen to the 3
  trades the spine actually takes.
- **Effective independent n ≈ 941 per direction**, not 94,314 (F-086's measured block
  autocorrelation: +0.292 at lag 1, +0.003 by lag 20). The block-permutation null is built on
  that measurement; an iid shuffle would have manufactured significance.
- **Selecting bars by realised outcome is lookahead by construction** (SEM-018). The holdout
  partition is what makes any forward reading possible, and it is single, not repeated.
- **The composite family is a function of the other ten**, so its test is not independent. It is
  counted inside the 22 and inside the pass ceiling rather than presented as extra evidence.
- **One instrument, one corpus, one config epoch.**
- mt00 **PARTIAL** (14 PASS, 0 FAIL, 2 structurally INCONCLUSIVE); mt01 **UNRUN** (0/27).

## What this does and does not do

Does **not** reopen F-086 — it asks a different question (incremental value *orthogonal* to CRT
state) and a null here is consistent with, not additional to, that finding. Does not retune any
SEM object. Does not touch a production config. Does not add a canonical feature dimension.

`context_attribution.promoted_families` stays **empty**, which is requirement 8 made mechanical.

## Artifacts

`docs/research-readiness/context_attribution/mc_ctxattr_xauusd_m15_v1/` —
`metrics.json`, `ledger.jsonl` (22 rows), `population_fingerprint.json`, `split_manifest.json`,
`mt00.json`, `mt01.json`, `run_manifest.json`, `RUN_SHA256.txt`.
Execution recorded in `configs/research/measurement_result_log.jsonl`.
