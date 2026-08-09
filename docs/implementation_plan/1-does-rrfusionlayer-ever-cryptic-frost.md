# Plan — RR fusion confidence-gate mis-specification: probe (hard gate), provisional finding, deferred fix

## Context

A forensic Q&A about `RRFusionLayer` (the F-038 "RR is a Gaussian duplicate" mechanism) surfaced a
root cause deeper than the recorded one. The code proves:

- **Base `RREngine`** (`src/engines/rr_engine.py`) is a stateless **Candle Polarity Index** (reads
  only `close/high/low`, no ML, no training) — NOT the 38-feature ML model. Independent fusion
  input; nothing to retrain/retire.
- **The RR ML model** (`NanoInferenceEngine`, `src/config_layer/rr/rr_pattern_miner.py`) IS trained
  on the real 38-dim canonical vector (`models/rr_model.json`: `n_features=38, n_train=49000,
  canonical_38`, 11 `zero_indices`). Not 3 features.
- **Hypothesised root cause (math-derived, empirically-UNconfirmed):** the confidence gate
  `confidence = exp(-0.5·d_sq)`, bypass if `< 0.3` (`rr_pattern_miner.py:339-342`), requires
  `d_sq < 2.408`. `d_sq` is Mahalanobis over **27 effective dims** whose in-distribution
  `E[d_sq]=27` → in-distribution confidence ≈ `exp(-13.5) ≈ 1.4e-6 ≪ 0.3` → the gate bypasses to
  Gaussian for ~**every** input, including in-sample. The observed "~5e-5 with the full vector"
  (F-038) ≈ the **expected in-distribution floor** for ~27 dof — evidence the **gate is mis-scaled**,
  not that the model is OOD/feature-starved.

**Static dof pre-check — already CONFIRMED (read-only, done during planning):** `models/rr_model.json`
has `len(conf_mu)=len(conf_P)=38`, dense 38×38 precision, and `scale_sigma==1` at **exactly** the 11
`zero_indices` (constant-zero columns). Zeroing precedes standardization ⇒ `delta[i]=0` for those
dims ⇒ they null their row+column in `conf_P` ⇒ the quadratic form has **rank 27**. So `E[d_sq]≈27`
is structurally sound. **Remaining unknown = the empirical in-sample `d_sq`/bypass distribution.**

**Outcome intended:** *first* confirm the bypass empirically on training data; *only if confirmed*
record the corrected mechanism as a finding and re-specify the gate — additively, behind config,
with `rr_fusion` staying `enabled=false` (the fix grants NO authority per §6.5 Authority Ladder).

**Non-goals:** retraining; removing the fallback (Option B hard-fails ~100% of decisions under any
gate); retiring the CPI; re-enabling `rr_fusion`.

---

## ⛔ Governing rule for this plan

**Track 1 is the hard gate.** If the in-sample probe does **not** show **≥95% bypass**, Tracks 2 and
3 **STOP** — the dof hypothesis is incomplete and must be re-derived before any finding or code
change. No math-first promotion: `Evidence → Finding → Math`, never `Math → Finding → Evidence`.

Revised execution order:
```
Track 1 (probe + training-stat validation)  ──PASS(≥95%)──▶  Track 2 (register)  ──▶  Track 3A (choose gate math)  ──▶  Track 3B (implement)  ──▶  Track 4 (future, out of scope)
        └── FAIL ─▶ STOP: re-derive dof hypothesis, revise plan
```

---

## Track 1 — Empirical probe + training-stat validation (read-only, HARD GATE)

**1A — In-sample bypass (decisive).** A model cannot be OOD on its own training data.
- New read-only script `scripts/analysis/rr_confidence_probe.py`:
  - `NanoInferenceEngine.load("models/rr_model.json")`; load training vectors `X` from
    `models/BNBUSDT/bnbusdt_balanced_20260524/rr_dataset_202605_v1.json` (version `202605_v1`).
  - Run each `X[i]` through the engine; record `d_sq`, `confidence`, `status`. Also run the 3-feature
    `score_dict` stub for contrast.
  - Emit `results/rr_confidence_probe/report.{json,md}`: **bypass fraction**, `d_sq`/`confidence`
    percentiles (min/median/p95/max), effective dof, full-vector vs 3-feature comparison.
- **1B — Training-stat validation (static half already confirmed above):** the script also asserts
  `len(conf_mu)==len(conf_P)==38`, `conf_P` is 38-wide, and the constant-zero columns == `zero_indices`
  (11) → effective dof 27. Record in the artifact so the dof argument is auditable.
- **GATE:** proceed only if in-sample bypass **≥95%** AND median `d_sq` ≈ dof (≈27). Otherwise STOP.

Read-only re: repo code; artifact under `results/` (gitignored data class).

## Track 2 — Register PROVISIONAL finding + refine F-038 + fix doc-drift  *(only if Track 1 PASSES)*

Run the E-001 6-question pre-registration ritual first (`docs/governance/EPISTEMIC_INTEGRITY.md`).

- **F-044 registered as PROVISIONAL / HYPOTHESIS**, not `Certain`, in BOTH enforced locations
  (`docs/current-findings.md` + `CLAUDE.md` §6.2 truths index; sync enforced by
  `tests/test_current_findings.py`):
  - Status `HYPOTHESIS`; **Promotion criterion explicit in the row:** "→ `Certain` iff Track-1
    in-sample bypass ≥95% (artifact `results/rr_confidence_probe/report.json`)."
  - Since Track 2 runs only after the ≥95% gate passes, the promotion criterion is met at
    registration — but the row records the criterion + artifact so authority is traceable to
    measurement, not math.
  - Conclusion: *the RR-fusion confidence gate is mis-specified for its dimensionality —
    `exp(-0.5·d_sq)<0.3` needs `d_sq<2.4` but the 27-rank Mahalanobis `E[d_sq]≈27`, so it bypasses to
    Gaussian for ~100% of inputs including in-sample; the F-038 double-count is a gate-scaling
    defect, not model OOD/feature starvation → retrain/full-vector cannot lift confidence under this
    gate.* Evidence = probe artifact + `file:line`.
- **Refine F-038 (not reverse):** append a `CORRECTED:` clarification to F-038's row +
  `docs/current-findings.md` — mechanism refined from "model OOD when fed correctly" to "gate
  mis-scaled to dimensionality; ~5e-5 ≈ expected in-dist floor for ~27 dof." Preserve history (§6.2
  rule 4); the disable-remediation stays correct.
- **Fix DOC_DRIFT (hash-neutral comments):** `rr_pattern_miner.py:4`/`:255` "24-feature" and `:18`
  "currently 35" → 38 (truth: `feature_schema.py:76`).

## Track 3A — Choose gate math from the MEASURED distribution  *(only if Track 1 PASSES)*

Do **not** pre-commit a gate formula. Read the probe's `d_sq` distribution, then select:
- `chi2_tail` (theory-expected): bypass if `Q(dof/2, d_sq/2) < p_threshold` — Mahalanobis→χ²→tail
  probability is exactly what the model implies. Preferred if median `d_sq ≈ dof`.
- `dof_scaled` (pragmatic): compare `d_sq/dof` to a threshold — sufficient if the distribution is
  well-behaved and a simple normalization separates in/out cleanly.
- Output: a one-paragraph decision note in the probe artifact naming the chosen mode + threshold,
  justified by the measured percentiles.

## Track 3B — Implement the chosen gate (additive, config-behind, parity-proved)

- `src/config_layer/rr/rr_pattern_miner.py`: extract the bypass decision into a pure-Python helper
  (inference is deliberately numpy-free / `__slots__`), modes:
  - `legacy_scalar` (**default**): `confidence < _CONF_BYPASS` — byte-identical to line 342.
  - the mode chosen in 3A (`chi2_tail` needs a ~20-line pure-Python regularized upper incomplete
    gamma; `dof_scaled` is trivial).
- **Config:** new `rr_model.confidence_gate` subsection in `configs/production/v2_multi_2026_04.json`,
  strict `_require`/`from_prod_config` — **no silent defaults** (§6.5 A1). Default
  `mode:"legacy_scalar"` → parity.
- **Hash:** `python scripts/maintenance/_compute_hash.py --check`; rehash only if `rr_model`
  participates.
- **`rr_fusion.enabled` stays `false`.** Correctness ≠ authority (§6.5). Re-enable is Track 4.
- **Parity proof (§6.5):** `mode="legacy_scalar"` + strict read + byte-identical `predict()` on the
  probe rows + determinism/replay gate green.
- **Tests** `tests/test_rr_confidence_gate.py`: legacy parity (full-object identity), chosen-mode math
  (known `d_sq`→expected bypass), missing-key raises. Keep green:
  `tests/test_rr_fusion_full_vector.py`, `tests/test_engine_runner_rr_fusion.py`,
  `tests/test_current_findings.py`, `tests/governance/test_epistemic_invariants.py`.

## Track 4 — Future retrain / re-enable  *(OUT OF SCOPE — not this plan)*

Any re-enable of `rr_fusion` requires a **measured ΔG001** improvement (Authority Ladder), gated
separately after the gate is correct. Listed only to fence it off.

---

## Critical files

| File | Track | Change |
|---|---|---|
| `scripts/analysis/rr_confidence_probe.py` | 1 | **new** read-only probe + stat validation |
| `results/rr_confidence_probe/report.*` | 1 | **new** artifact = promotion gate for all later tracks |
| `docs/current-findings.md` | 2 | add F-044 (HYPOTHESIS), refine F-038 |
| `CLAUDE.md` (§6.2 truths index) | 2 | F-044 row + promotion criterion, F-038 clarification |
| `src/config_layer/rr/rr_pattern_miner.py` | 2,3B | doc-drift fix; dof-aware gate helper + modes |
| `configs/production/v2_multi_2026_04.json` | 3B | `rr_model.confidence_gate`, default legacy |
| `tests/test_rr_confidence_gate.py` | 3B | **new** parity + gate math |

## Verification (end-to-end)

1. `python scripts/analysis/rr_confidence_probe.py` → **GATE:** in-sample bypass ≥95%, median `d_sq`≈27,
   dof-stat assertions pass. If FAIL → STOP.
2. `pytest tests/test_rr_confidence_gate.py -q` → parity + chosen-mode math pass.
3. `pytest tests/test_current_findings.py tests/governance/test_epistemic_invariants.py -q` → green.
4. `pytest tests/test_rr_fusion_full_vector.py tests/test_engine_runner_rr_fusion.py -q` → no regression.
5. Determinism/replay gate (BNBUSDT+SOLUSDT) byte-identical with `mode="legacy_scalar"`.
6. `python scripts/maintenance/_compute_hash.py --check` → unchanged, or rehash if `rr_model` participates.
7. SESSION LOG appended to `assistant_project.md` (§6); §6.2 doc-decision audit entry recorded.

## Governance notes
- **Track 1 is the promotion gate for every subsequent change.** No finding/code before ≥95% bypass.
- F-044 enters as HYPOTHESIS with an explicit, artifact-linked promotion criterion.
- F-038 is refined (mechanism), not reversed; history preserved (§6.2 rule 4).
- Gate fix grants tunability, not authority; `rr_fusion` stays disabled. Re-enable = Track 4, ΔG001-gated.
- E-001 pre-registration ritual precedes registering F-044.
