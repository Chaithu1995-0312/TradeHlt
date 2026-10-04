# Object: context feature attribution overlay (SEM-036)

**Frozen 2026-08-29.** Contract `MC-CTXATTR-XAUUSD-M15-V1`. Change
`CH-v3-unified-market-structure-v1`. Code `src/research/evidence/context_attribution.py`.

Research authority only. `economic_claims_allowed` is false; mt01 is 0/27, so the E4 seal is
unmet regardless of outcome.

---

## What the object is

For one context family `f` and one direction `d`, a **mean-preserving size overlay** applied
inside each CRT-state stratum:

```
w        = 1 + k   when agree_f(bar, d) is True
           1 - k   when it is False
           excluded when it is None            (no reading — never "disagree")

k        = 0.5, frozen (research.evidence.magnitude_prior.OVERLAY_K)

per stratum s:  y~ = y - mean_s(y)                     # centered
                delta_s = E_s[w·y~] - E_s[y~]
                (skipped entirely when the context does not vary in s)

PRIMARY  delta_within_stratum = Σ_s n_s · delta_s / Σ_s n_s
DIAGNOSTIC delta_marginal     = the same overlay ignoring strata
           crt_proxy_component = delta_marginal - delta_within_stratum
```

## Why it is built this way

**The stratum is the answer to "beyond CRT alone".** Conditioning on `crt_state_after` and
measuring inside it means a family cannot score by proxying for CRT state — that is removed by
construction, not argued away in a caveat. `delta_marginal` is kept precisely so the removed
part is visible rather than invisible.

**Centering is load-bearing, not cosmetic.** Uncentered, the delta is
`k · (n_a·mean_a − n_d·mean_d) / n`, which for an information-free context
(`mean_a == mean_d == m`) reduces to `k · m · (n_a − n_d) / n`. The stratum means here reach
−0.29R, so a family with no information and a lopsided agree/disagree split would score a
spurious effect of roughly the magnitude being hunted. Centering makes the delta zero exactly
when the agree-cell mean equals the stratum mean, which is the definition of "no within-stratum
information".

**Single-cell strata are skipped.** If every row in a stratum agrees, the overlay is a uniform
`1+k` rescale, not a contrast. Folding it in would report `k` itself as an effect.

Both properties were found by the orthogonality floor on a planted confound *before any outcome
was computed*, and the amendment is recorded in the contract's `authority.note`. The floor
plants a case where the context has no within-stratum effect but agreement concentrates in the
high-mean stratum with 180/20 cells; the marginal reading is large, the primary must be exactly
zero.

**A `None` verdict is an abstention.** Most SMC zones are absent on most bars. Counting an
absent zone as a disagreement would convert "we could not look" into evidence against the
family — the single easiest way to manufacture a result here.

## The population, and why it is inverted

Unit = (bar, direction). Not detector-selected: the CRT executed-trade ledger holds **3 trades
in 47,275 XAUUSD M15 bars**, so eleven families against it is not a study. Labels come from
SEM-018's oracle at the PRIMARY arm (`disp_bar`, `production`), walked by `multi_tp_walk`
(SEM-017) under the production two-target geometry, net of SEM-015 measured cost with SEM-016
adverse fills. Context comes from the SEM-035 snapshot, joined on `bar_index` within one
`run_id` and one `corpus_sha256`.

**This measures the every-bar population, not production's executed trades.** Nothing derived
from it describes what the spine would do.

## The 11 families

Ten single-family predicates — `parent_crt`, `htf`, `objective`, `fvg`, `order_block`,
`breaker`, `mitigation`, `choch`, `eqh_eql`, `pdh_pdl` — each declared in the contract's
`features.name_binding` before any y was seen, plus a `composite` majority vote.

The composite is a **function of the other ten**, so its test is not independent of them. It is
counted inside the 22 pre-registered tests and inside the pass-count ceiling rather than
presented as separate evidence.

## Gate (frozen)

Per family × direction, on holdout units only, all four:

1. agree-cell n ≥ 30 **and** disagree-cell n ≥ 30;
2. `sign(holdout delta_within_stratum) == sign(train …)`;
3. survives BH-FDR at q=0.10 across all 22, p from a block-permutation null (block 40 bars,
   199 perms — block because F-086 *measured* the autocorrelation, +0.292 at lag 1 → +0.003 by
   lag 20, giving effective n ≈ 941/direction);
4. magnitude exceeds **both** the `long_only` and shuffled-context controls.

`E > 0` is deliberately **not** a clause: the base rate is ≈ −0.29R, so beating it means losing
less, not earning. `long_only` is the binding control because XAUUSD rose across the corpus and
zero is the wrong reference (F-086 saw positive counts collapse 65→8, 56→1, 2→0 against it).

More than **6 of 22** passing is pre-registered as a suspected multiplicity artifact, not a set
of discoveries.

## Not

Not a side picker. Not a sizing rule. Not a fusion weight. Not `delta_marginal`. Not a claim
about production trades. Not `crt_state_resolved` (that is the resolver — F-069, F-086).
Not F-086's 236-bar stride holdout, which stays unspent.

## What a pass would authorize

Exactly one thing: opening a **separate, separately-authorized** change program to wire that
family into decision logic. It would not grant G001, would not flip
`economic_claims_allowed`, and would not itself change
`context_attribution.promoted_families`.

## Result

See [F-097](../current-findings.md) and
[`docs/analysis/context-attribution-holdout-2026-08-29.md`](../analysis/context-attribution-holdout-2026-08-29.md):
**0 of 22, powered**.
