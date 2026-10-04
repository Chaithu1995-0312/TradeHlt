# ZONE-X DECISION RECORD — 2026-08-06

**Status:** BINDING for programme direction (research only; does **not** amend frozen `ZONE-X-SPEC-v0.8.md`).  
**Inputs:** `ZONE-X-SPEC-v0.8.md`, `ZONE-X-KNOWLEDGE-TRANSFER.md`, `ZONE-X-COST-NOTE.md`, `ZONE-X-DESIGN-CONTINUATION-v0.9.md`.  
**Operator decision** (this document freezes the choice in writing).

---

## 1. Decisions

| ID | Decision | Value |
|---|---|---|
| **D-C1** | Research / design default cost | **`c = 0.055 ATR/side`** |
| **D-C2** | Empirical baseline (report & benchmark) | **`c = 0.0238 ATR/side`** |
| **D-C3** | Optional stress / legacy reference | **`c = 0.070 ATR/side`** (v0.8 working assumption) |
| **D-P1** | Programme path (transfer §9.2) | **(a) Stop** |
| **D-S1** | Sensitivity protocol | Key experiments reported at **{0.0238, 0.055, 0.070?}** |
| **D-S2** | Stability criterion for ontology inclusion | A label/strategy that **flips material conclusions** across the cost grid is **execution-sensitive** → treat cautiously; one that is **stable** across the grid is a **stronger** ontology candidate |

### Rationale (operator, paraphrased)

- Demo O-1 measured median stop slip → `c ≈ 0.0238` ATR (half-spread + commission + stop median).
- Stop sample is thin (n=7 near-market demo fills) and likely **understates** gap-driven barrier slip; p90 stop slip → `c ≈ 0.055`.
- Until a **substantially larger sample of live stop executions across volatility regimes** exists, design defaults to the **conservative** 0.055 figure.
- Keep 0.0238 as the **empirical baseline** for reporting and benchmarking (what the terminal actually showed under the measurement protocol).
- Path **(a)**: do not open a declared-prior search on gold M15 under ZONE-X; the registered §6 null stands; cost unblocking does not create a hunting license.

---

## 2. Cost triple (provenance — do not re-derive as novel)

From `ZONE-X-COST-NOTE.md` / manifest `20260806T084013Z` (ICMarketsSC-Demo, XAUUSD):

| Component | $/oz/side | Notes |
|---|---|---|
| Half-spread | 0.045 | median full spread $0.09 |
| Commission | 0.040 | $4/lot/side ÷ 100 oz; abs of MT5 signed debit |
| Stop slip median | 0.090 | n=7 seeded near-market STOPs |
| Stop slip p90 | 0.320 | used for stress `c` |

```
c_empirical = (0.045 + 0.040 + 0.090) / 7.342 = 0.175 / 7.342 = 0.0238 ATR   (D-C2)
c_design    = (0.045 + 0.040 + 0.320) / 7.342 = 0.405 / 7.342 = 0.0552 ATR   (D-C1 ≈ 0.055)
c_legacy    = 0.070 ATR                                                      (D-C3, v0.8 §8)
```

ATR citation: v0.8 §3.2 median **$7.342** (frozen; not recomputed).

---

## 3. Thresholds under the three cost points

Directional, `k=1.5`, `m=1.0`, generation long baseline **0.4071** (v0.8 §5.2):

| `c` ATR/side | Role | `p* = (1+c)/2.5` | gap vs long 0.4071 | Straddle lift `2c` |
|---|---|---|---|---|
| **0.0238** | Empirical baseline (D-C2) | 0.4095 | **+0.24 pp** | 0.0476 |
| **0.055** | Design default (D-C1) | 0.4220 | **+1.49 pp** | 0.110 |
| **0.070** | Legacy / optional stress (D-C3) | 0.4280 | **+2.09 pp** | 0.140 |

Interpretation under path (a): these numbers are **reporting / sensitivity scaffolding**, not a mandate to re-open search. Any future work that *does* touch economics must show the grid (D-S1).

---

## 4. Path (a) — stop protocol (executed by this decision)

Per design continuation §8 and transfer §9.2(a):

1. **FEATURE_SEARCH_HALTED_ON_NULL** remains in force on XAUUSD M15 under ZONE-X branding.
2. §6 eight-feature null stays registered (`S-13`); do not re-report as novel.
3. Test year remains **sealed** (no need to unseal for a stop).
4. **Allowed residual work** (non-search):
   - Maintain O-1 tooling and accumulate larger **live** stop-fill samples (may revise D-C1 later).
   - Optional descriptive O-4 gap study (no X-seeking).
   - Apply **D-S1 / D-S2** whenever a *separate* programme (e.g. ontology / labeling) scores economics on gold.
5. **Forbidden without a new decision record:**
   - Open-ended geometry search on gold M15 as ZONE-X continuation.
   - Declared-prior campaign (path b) without superseding this record.
   - Treating `c=0.0238` alone as production/design truth while stop sample stays thin.

### Reopen conditions (explicit)

Path (a) may be reopened only by a **new dated decision record** if any of:

| Trigger | Possible new path |
|---|---|
| Live stop-fill sample large enough that design `c` revises **materially** (e.g. stabilizes near 0.0238 across regimes) | reconsider (b) under design table |
| Operator chooses venue/timeframe change | (c) |
| Operator explicitly authorizes declared-prior campaign with M-cap | (b) |

Thin sample alone improving by a few more demo fills is **not** sufficient reopen.

---

## 5. Sensitivity protocol (D-S1 / D-S2) — permanent research rule

Whenever a key experiment reports economic or labeling conclusions that depend on round-trip cost:

### 5.1 Grid (required)

| Point | `c` ATR/side | Label in artifacts |
|---|---|---|
| Empirical | **0.0238** | `c_empirical` |
| Design default | **0.055** | `c_design` |
| Optional legacy | **0.070** | `c_legacy` (include when comparing to v0.8 literature) |

Primary narrative uses **`c_design`**. Tables always include at least `c_empirical` and `c_design`.

### 5.2 Stability classification (D-S2)

For each strategy / label / semantic rule `R`, after evaluating the grid:

| Class | Definition | Ontology posture |
|---|---|---|
| **COST_STABLE** | Sign of edge, promote/reject, or membership ranking **unchanged** across {0.0238, 0.055} (and 0.070 if run) | Stronger candidate for ontology inclusion |
| **EXECUTION_SENSITIVE** | Material flip (sign, pass/fail, or rank inversion) across the grid | Cautious; do not promote into ontology on a single-`c` story |
| **INCONCLUSIVE** | Underpowered at one or more grid points | No ontology claim |

**Material** means: changes a pre-declared decision (PASS/FAIL, include/exclude, or rank-1 identity), not a cosmetic change in third decimal of EV.

### 5.3 What this is not

- Not a license to search features until something is COST_STABLE.
- Not an amendment of v0.8 `c=0.07` as historical text — v0.8 stays frozen; this record **supersedes it for forward work**.
- Not production authority (§6.5 ladder still applies if anything ever touches the spine).

---

## 6. Programme status summary

| Item | Status after this decision |
|---|---|
| O-1 | **Unblocked** (MEASURED demo triple; design uses stress `c`) |
| O-2 (continue past null?) | **Answered: no** — path (a) |
| Feature search XAUUSD M15 ZONE-X | **HALTED** |
| Test year | **Sealed** |
| Declared-prior register | **Not opened** |
| O-4 descriptive | **Done 2026-08-06** — avg realized_m≈m; P(gap_through)≪0.1%; does not revise D-C1 |
| Next default work | Accumulate live stop samples; apply cost grid to any *other* gold economic claims |

---

## 7. One paragraph

O-1 was measured on the IC Markets demo: empirical all-in cost ≈ 0.0238 ATR/side, but stop slippage rests on only seven near-market fills, so the operator adopts 0.055 ATR/side (p90-implied) as the research default and keeps 0.0238 for reporting. Path (a) stops further ZONE-X geometry search on gold M15; the §6 null stands. Any future economic or labeling claim that depends on cost must be shown on the {0.0238, 0.055, optional 0.070} grid; stability across that grid is required before treating a rule as ontology-ready.

---

## 8. Change log

| Date | Change |
|---|---|
| 2026-08-06 | Initial binding decision: D-C1/C2/C3, path (a), sensitivity protocol D-S1/D-S2. |
