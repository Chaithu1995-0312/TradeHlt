# Blind-label instrument — governance defect, and which program replaces the gate

> **State: UNKNOWN.** P1 has not succeeded and has not failed. Zero annotations exist. The correct
> status is *unevaluable*, and it stays unevaluable until a new contract is registered.

## What was established (measured, not argued)

### D1 — the gate is unevaluable (both rules agree)

`blind_label_score.py` `MIN_CELL_N = 15`; Arm C contributes one pair per Arm-C item → **n = 10**.
Proven empirically with a synthetic **perfect-label** set through the *unmodified* scorer: all four
questions returned `INSUFFICIENT`, κ=`None`, while Arm A scored normally at n=60. So the defect is
Arm C's allocation, not a broken scorer.

### D2 — the scorer does not implement its own registration (new, and worse)

| | Rule |
|---|---|
| Pre-registration says | *"Any scored cell with **< 15 minority-class instances** is reported `INSUFFICIENT`"* |
| Scorer does | `n = len(y_true); if n < MIN_CELL_N` — **total n**, not minority-class |

These are different rules, and the difference is material on **6 of 12 cells — every one in the
over-reporting direction**, i.e. the scorer would publish a κ the registration says must not be
trusted:

| Arm | Question | Class counts | Minority | Scorer | Prereg |
|---|---|---|---|---|---|
| A | `q3_sweep` | 0:50, 1:6, −1:4 | **4** | SCORED | **INSUFFICIENT** |
| A | `q4_bos` | 0:42, 1:13, −1:5 | **5** | SCORED | **INSUFFICIENT** |
| B | `q1_trend` | 1:17, −1:13 | 13 | SCORED | **INSUFFICIENT** |
| B | `q2_vol` | 2:14, 1:10, 0:6 | 6 | SCORED | **INSUFFICIENT** |
| B | `q3_sweep` | 0:13, −1:9, 1:8 | 8 | SCORED | **INSUFFICIENT** |
| B | `q4_bos` | 0:15, 1:9, −1:6 | 6 | SCORED | **INSUFFICIENT** |

Arm C agrees under both rules; Arm A `q1`/`q2` pass under both.

**This inverts which defect matters more.** The Arm C gate is *protective* — it blocked the run.
D2 is the opposite: it silently produces numbers. Had the gate not fired, the program would have
published 6 κ values in violation of its own registered interpretation rule.

### D3 — the sample is undersized for its own rule on two questions

Arm A is uniform-random, so it preserves true base rates. Items required for
minority-class ≥ 15:

| Question | Rarest class | Base rate | Items needed | Have (Arm A) |
|---|---|---|---|---|
| `q1_trend` | 27/60 | 45.0% | ~33 | 60 ✅ |
| `q2_vol` | 16/60 | 26.7% | ~56 | 60 ✅ |
| `q3_sweep` | 4/60 | **6.7%** | **~225** | 60 ❌ |
| `q4_bos` | 5/60 | **8.3%** | **~180** | 60 ❌ |

So under its own registered rule the instrument can deliver **Q1 and Q2 at current size**, and
**cannot deliver Q3 or Q4 without ~3–4× more items** — for either labeler.

## Why the A/B framing needs correcting

**Option A alone (resample Arm C ≥ 15) is not merely insufficient — it is actively harmful.** It
removes the block while D2 remains, converting a program that correctly refused to report into one
that reports 6 untrustworthy cells.

**Option B is mis-named.** Nothing needs *redefining*: the pre-registration already defines the
rule. The scorer simply does not implement it. Order of operations in the human prereg confirms the
registration was written first (step 1) and the sampler/scorer generated after (step 3), so the
scorer is the side that diverged. **B is a bug fix, not a metric change** — which matters, because
"redefining a metric after seeing it block you" is threshold-shopping, while "making the code match
the registration" is the opposite.

## Recommended: B first, then a sizing decision — as ONE new registration

Both defects are in the shared instrument, so they are one program, not two.

1. **Fix `_kappa` to implement the registered rule** — gate on minority-class count, not total n.
   Necessary regardless of what else is decided, and it makes the instrument *stricter*, never
   looser. Add a floor test asserting the 6 cells above report `INSUFFICIENT`.
2. **Then choose the sizing contract**, with the numbers above in hand:
   - **Scope to Q1+Q2**, which the current sample already satisfies — but Arm C still needs
     ~56 pairs for `q2` (~33 for `q1`) to give those questions a valid ceiling; or
   - **Resample at ~225 items** so all four questions clear the registered rule; or
   - **Accept Q3/Q4 as permanently INSUFFICIENT** at practical size and register that as the
     finding — itself a legitimate, publishable result about the instrument.
3. **Neither may retro-fit** `preregistration-llm-blind-label-annotator.md` or the human prereg.
   Both stay frozen; the halt record stays as written; the new contract is a new document.

## Critical files (for the new program, when authorised)

- `scripts/analysis/blind_label_score.py` — `_kappa`, `MIN_CELL_N`, `QUESTIONS`
- `scripts/analysis/blind_label_sample.py` — only if resampling is chosen
- `results/blind_label/sample_manifest.json` — the frozen answer key (arm counts, `repeat_of`)
- `tests/test_blind_label_harness.py` — already has scorer sanity tests
  (`test_scorer_reports_insufficient_below_min_n`) that must be extended, not replaced
- Both existing pre-registrations — **read-only**

## Verification (for the new program)

- The 6 D2 cells flip to `INSUFFICIENT` under the corrected rule; Arm A `q1`/`q2` stay `SCORED`.
- A perfect-label round-trip still scores Arm A `q1`/`q2` — the fix must not make everything
  insufficient (that would be a different failure).
- `test_scorer_reports_insufficient_below_min_n` extended to cover minority-class, not just total n.
- Arm C remains `INSUFFICIENT` unless the sizing contract explicitly resamples it.
- No diff to either pre-registration; no diff to `sample_manifest.json` unless resampling is the
  chosen contract, in which case it is a *new* manifest, not an edit.

## Explicitly out of scope

- Any LLM annotation. The gate is unevaluable; nothing may be annotated against it.
- Lowering `MIN_CELL_N` to make cells pass — the direction the evidence forbids.
- Reporting any κ from the current instrument.
