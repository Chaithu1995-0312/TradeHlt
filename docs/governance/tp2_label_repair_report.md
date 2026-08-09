# Phase A — TP2 Label Repair (Root Cause)

| Field | Value |
|-------|--------|
| Date | 2026-07-22 |
| Dataset examined | `TN_ENV_CLEAN_L1` BNBUSDT n=139,942 |
| Authority | Research / protocol only |

## 1. Root-cause analysis

### Pipeline trace

```text
opportunities.jsonl
  → unit geometry: entry, sl, tp  (no tp2 field)
  → builder label_one_unit:
       risk = |entry − sl|
       tp1_mult = |tp − entry| / risk
       walk_TP1: forward_walk(SL=1R, TP=tp1_mult·R)
       walk_TP2: forward_walk(SL=1R, TP=TP2_ATR_MULT·R)   # L1: TP2_ATR_MULT=2.0
       y_tp1 = (walk_TP1.outcome == TP_HIT)
       y_tp2 = (walk_TP2.outcome == TP_HIT)
```

### Measurement (not guesswork)

| Check | Result |
|-------|--------|
| `tp1_mult` on clean dataset (50k + 28k subsample) | **exactly 2.0** for 100% of rows |
| Source opportunities (20k lines) | **exactly 2.0** for 100% of geometry-ok units |
| L1 `TP2_ATR_MULT` | **2.0** (`SURROGATE_2R_BEFORE_SL`) |
| Implication | `walk_TP1` ≡ `walk_TP2` (same SL, same TP) |
| Observed TP1↔TP2 Spearman | ≈ **0.9996** |
| Residual disagrees | floating dust only (~0.016%) |

### Cause classification

| Candidate | Verdict |
|-----------|---------|
| Label protocol (L1 surrogate = 2R) | **PRIMARY** — surrogate equals unit TP by construction on this corpus |
| Source geometry (unit TP always 2R) | **PRIMARY co-cause** — population has no distinct TP1/TP2 ladder |
| `forward_walk` implementation | **Not causal** — kernel is correct; both walks receive identical levels |
| Event ordering / exit policy | **Not causal** — same `intrabar_fixed` on both walks |
| Replay logic | **Not causal** |

**Conclusion:** Collapse is a **protocol + population geometry** defect, not a walk bug.  
L1 chose `SURROGATE_2R` because no `tp2` field existed (GATE-0). On BNBUSDT opportunities, unit reward is **hard-coded 2R**, so the surrogate is a no-op.

Protocol L1 is **internally consistent** with its freeze text, but **semantically defective** for a three-head TradeNet (two heads are the same random variable).

---

## 2. Proposed protocol correction

| Field | L1 (superseded for new work) | **L2 (repair)** |
|-------|------------------------------|-----------------|
| `protocol_id` | `TN_ENV_CLEAN_L1` | **`TN_ENV_CLEAN_L2`** |
| `tp2_policy` | `SURROGATE_2R_BEFORE_SL` | **`STRETCH_3R_BEFORE_SL`** |
| `tp2_atr_mult` | 2.0 | **3.0** |
| `y_tp1` | unit TP before SL (empirically hit 2R) | **unchanged** (unit geometry) |
| `y_tp2` | hit 2R before SL | **hit 3R before SL** (strict stretch beyond unit TP) |
| Other labels | — | **unchanged** |
| Envelope labels | — | **unchanged** |

### Why 3R (not drop head / not horizon flag)

1. **Nesting:** on a continuous favorable path, 3R requires passing 2R → `y_tp2=1 ⇒` path had room for unit TP; rates should satisfy `rate(tp2) < rate(tp1)` when unit TP=2R.
2. **Distinct Bernoulli:** not a re-encode of `y_reached_2r_horizon` (exit-agnostic) — still SL-gated via `forward_walk`.
3. **Keeps three-head composite shape** `(0.4, 0.4, 0.2)` with honest meanings: unit target / stretch / BE survival.
4. **Dropping y_tp2** is a valid alternative (two-head) but throws away the stretch question TradeNet was designed to ask.

L1 artifacts remain valid under their hash (historical). **GATE-O must use L2 only.**

---

## 3. Expected behavioral change

| Metric | L1 | L2 expected |
|--------|----|-------------|
| TP1↔TP2 correlation | ≈1.0 | **≪ 1** (related, nested) |
| `rate(y_tp2)` | ≈ `rate(y_tp1)` ≈ 0.33 | **strictly lower** than y_tp1 |
| P(tp2 \| tp1) | ≈1.0 | **< 1** |
| P(tp1 \| tp2) | ≈1.0 | **≈1** (nested: 3R hit ⇒ path cleared 2R before SL on stretch walk; not identical to unit walk exit) |
| Envelope labels | — | **byte-stable** if only TP2 walk changes |

---

## 4. Risks

| Risk | Mitigation |
|------|------------|
| 3R is still “invented” (no product TP2) | Declared `STRETCH` policy; research stretch, not broker TP2 |
| Nested labels → multicollinearity in multi-head nets | Expected; evaluate marginal value of y_tp2 in GATE-O |
| Breaks L1 comparability | New `protocol_id` / hash; never mix epochs |
| Sparse positives at 3R | Report class balance; may be rare → diagnostic head |

---

## 5. Recommendation

**REPAIR → L2 `STRETCH_3R_BEFORE_SL`.**  
Do not run GATE-O on L1 outcome heads. Rebuild clean labels under L2, then nonlinear probes.

---

## 6. Proof that collapse is not “legitimate three-head structure”

If TP1 and TP2 were intended as the same level, the composite would be mis-specified (double-counting).  
TradeNetV2 design (`p_tp1`, `p_tp2`, `p_survives_be`) requires **ordered path milestones**. L1 fails that requirement on this corpus. L2 restores order: BE (1R) ⊂ unit TP (2R) ⊂ stretch (3R) as path events under SL-gated walks (BE via `reached_1r` on unit walk; TP1/TP2 via respective walks).
