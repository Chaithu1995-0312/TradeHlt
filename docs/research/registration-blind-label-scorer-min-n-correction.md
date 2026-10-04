# Registration — Blind-Label Scorer: minority-class `INSUFFICIENT` correction

> **Status:** REGISTERED 2026-08-31, written **before** the fix was applied. Authority:
> research/docs only (§6.5 Authority Ladder). **CH-blind-label-scorer-min-n-v1.**
>
> This is a **defect correction to a shared instrument**, not a new experiment and not a metric
> redefinition. It produces no κ, no annotation, and no claim about any labeler.

## Why this document exists

`scripts/analysis/blind_label_score.py` is declared frozen by **both** blind-label
pre-registrations — *"a diff on the scorer invalidates any run made against this document."*
Changing it therefore requires its own record, written first, stating exactly what changes, why it
is a correction rather than a redefinition, and in which direction it can move results.

## The defect (measured 2026-08-31, during the halted P1 execution)

### D2 — the scorer does not implement its own registration

| | Rule |
|---|---|
| `preregistration-blind-label-descriptive-fidelity.md` says | *"Any scored cell with **< 15 minority-class instances** is reported `INSUFFICIENT`, never as a null result (E-001 discipline: underpowered ≠ negative)."* |
| `blind_label_score.py::_kappa` does | `n = len(y_true); if n < MIN_CELL_N: … INSUFFICIENT` — **total n** |

Two different rules. The pre-registration was written first (its own "Order of operations" step 1)
and the sampler/scorer generated afterwards (step 3), so **the scorer is the side that diverged**.

### Measured impact — 6 of 12 cells, all over-reporting

Computed from the frozen answer key in `results/blind_label/sample_manifest.json`:

| Arm | Question | Class counts | Minority | Scorer today | Registration requires |
|---|---|---|---|---|---|
| A | `q3_sweep` | 0:50, 1:6, −1:4 | **4** | SCORED | **INSUFFICIENT** |
| A | `q4_bos` | 0:42, 1:13, −1:5 | **5** | SCORED | **INSUFFICIENT** |
| B | `q1_trend` | 1:17, −1:13 | 13 | SCORED | **INSUFFICIENT** |
| B | `q2_vol` | 2:14, 1:10, 0:6 | 6 | SCORED | **INSUFFICIENT** |
| B | `q3_sweep` | 0:13, −1:9, 1:8 | 8 | SCORED | **INSUFFICIENT** |
| B | `q4_bos` | 0:15, 1:9, −1:6 | 6 | SCORED | **INSUFFICIENT** |

Every discrepancy is in the **publish-an-untrustworthy-κ** direction. Arm A `q1`/`q2` pass under
both rules; Arm C fails under both.

### Related, and NOT fixed here — D1 and D3

- **D1:** Arm C allocates 10 items → 10 pairs → `INSUFFICIENT` under either rule, so the
  intra-rater ceiling both programs treat as their interpretive floor is unevaluable. Proven with a
  perfect-label round-trip through the unmodified scorer.
- **D3:** Arm A preserves base rates, so minority-class ≥ 15 needs ~33 items for `q1`, ~56 for
  `q2`, but **~225 for `q3`** (6.7% rarest class) and **~180 for `q4`** — against 60 held.

Both are **sizing** questions. They are deliberately left open: this correction changes no sample.

## What changes

`_kappa` gains a minority-class check alongside the existing total-n check. Both must pass for a
cell to be `SCORED`. `MIN_CELL_N = 15` is **unchanged** — the threshold is not being tuned, only
applied to the quantity the registration names.

`status` becomes one of `SCORED` · `INSUFFICIENT` (total n) · `INSUFFICIENT_MINORITY` (the newly
enforced rule), so the two reasons stay distinguishable in the report rather than collapsing into
one label.

## Direction guarantee — why this cannot be threshold-shopping

Adding a second necessary condition can only move cells **SCORED → INSUFFICIENT**, never the
reverse. The instrument becomes **strictly stricter**. A change that made previously-blocked cells
pass would be threshold-shopping; this is provably incapable of it, and a floor test pins that.

## Safety of diffing a frozen instrument

Both pre-registrations bind future runs to the frozen scorer. This diff is safe **only because zero
annotations exist against either registration** — there is no result to retroactively void, and no
published κ changes value. That is a fact about timing, not a licence. After this correction the
frozen-instrument clause binds again, against the corrected scorer.

Neither pre-registration is edited. The P1 halt record stands as written.

## Verification (all must hold)

1. The 6 cells above report `INSUFFICIENT_MINORITY`.
2. Arm A `q1_trend` / `q2_vol` remain `SCORED` — the fix must not make everything insufficient,
   which would be a different failure wearing the same mask.
3. A perfect-label round-trip still yields κ = 1.0 on the cells that remain scorable.
4. Arm C stays `INSUFFICIENT` on all four questions (unchanged by this correction).
5. `tests/test_blind_label_harness.py::test_scorer_reports_insufficient_below_min_n` still passes,
   **extended** rather than replaced.
6. No diff to `sample_manifest.json`, `session_01.html`, `blind_label_sample.py`, or either
   pre-registration.

## Authority

Research/docs only. Produces no κ, no annotation, no economic claim. Grants nothing on the
Authority Ladder and cannot revise F-019…F-097. The sizing contract (D1/D3) remains **UNKNOWN** and
open, to be decided separately with the corrected instrument in hand.
