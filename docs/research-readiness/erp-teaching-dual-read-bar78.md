# ERP Teaching Example — Dual-Read Bar 78

> **Permanent ERP teaching card.** DESCRIPTIVE — information not authority (§6.5).  
> Parent chapter: [`ic-001-xauusd-static-entry-closure.md`](ic-001-xauusd-static-entry-closure.md)  
> Library: `results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md` exemplars **#1** and **#4**

---

## One-line lesson

> **Entry-time mathematics restates candle morphology; it does not adjudicate direction/family forks on the same vector.**

Use this as the **opening slide** for any IC-001 presentation, handoff, or LLM cold-start on the XAUUSD descriptive pack.

---

## The pair

| Aspect | Exemplar #1 | Exemplar #4 |
|--------|-------------|-------------|
| **Trade ID** | `expansion_breakout_000007` | `mean_reversion_000012` |
| **Library role** | `typical_tp` (+ tag `dual_read_bar_78`) | `dual_read` |
| **Entry index** | **78** | **78** |
| **Timestamp** | 2024-05-22 20:30:00 | **identical** |
| **Price** | 2387.55 | **identical** |
| **Family** | expansion_breakout | mean_reversion |
| **Direction** | **short** | **long** |
| **Outcome** | **TP_HIT** | **SL_HIT** |
| **R achieved** | +2.0 | −1.0 |
| **CRT** | 0.4503 | **0.4503** |
| **Gaussian** | 0.8821 | **0.8821** |
| **Zone** | 0.2 | **0.2** |
| **RR (polarity A)** | 0.7683 | **0.7683** |
| **Fusion composite** | 0.5616 | **0.5616** |

Key features at entry (shared): body_ratio≈0.576 · disp_strength≈0.374 · rsi_14≈38.6 (see exemplars JSONL for full 38-dim).

```text
Same bar
  → same 38 features
  → same engine scores
  → different direction / family
  → opposite outcome
```

---

## Why this is stronger than “AUC ≈ 0.51”

AUC≈0.51 is a **population** coin-flip. Dual-read is a **constructive counterexample**:

- Engines and features cannot be “wrong about the candle” — they describe the same candle twice.
- The fork is **assignment** (long vs short / family), not missing static structure on that bar.
- Any model that only sees the static entry vector is **structurally blind** to this fork.

---

## How to use

| Audience | Use |
|----------|-----|
| Human review | Opening slide; “what did IC-001 actually measure?” |
| LLM session | Paste this card before proposing entry models |
| Regression | `tests/research/test_erp_teaching_dual_read.py` — pair must stay consistent |
| Library navigation | Start with #1 vs #4, then high-agreement #10–#13 |

---

## Related teaching blocks (same library)

| Block | Exemplars | Lesson |
|-------|-----------|--------|
| High agreement TP/SL | #10–#13 | Engine alignment ≠ predictive skill |
| Near-miss | #5, #6, #7, #18, #28 | Path competence ≠ eventual TP |
| High disagreement | #14–#17 | Disagreement is not a reliable filter |

---

## Machine pointers

```text
results/research/trace_corpus/xauusd/representative_exemplars.jsonl
  trade_id = expansion_breakout_000007 | mean_reversion_000012
  entry_index = 78
  tags contain dual_read_bar_78
```

---

## Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Phase 1 permanent teaching card |
