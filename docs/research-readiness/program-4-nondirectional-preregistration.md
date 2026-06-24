# Program 4 — Non-Directional-Target Probe (regime-conditioned consumption) · PRE-REGISTRATION

> **Program 4 exists to test whether a predictable phenomenon can be converted into money
> inside a spot directional architecture. It does not test whether volatility is predictable,
> because that question has already been answered.**

Status: **PRE-REGISTERED (written before running)** · Date: 2026-06-17 · Branch: `patch`
Determinism: deterministic; the report body carries no wall-clock (matches `edge_report` discipline).

---

## 1. Why this program exists

Program 1 (next-bar **direction**, M15 crypto, intrabar+12bps) is KILLED after four
falsifications (F-019 entry / F-020 conditional / F-021 selection / F-025 exit). Program 2
(structural asymmetry, F-026) and Program 3 (HTF, F-027) are frozen. The legitimate reopen path
is a **new ontology**, not a parameter pass. Program 4 changes the **target**: from price
direction to a **non-directional volatility-regime state**, on the same frozen, trusted crypto
data and in the same court (unchanged `forward_walk` / `QualificationGate` / `CostModel`).

The prior is already measured (`process_characterization`): volatility has memory
(`H_atr≈0.885`) while direction does not (`H_returns≈0.527`), with the explicit caveat that at
large N *statistically significant ≠ economically exploitable*. **This probe closes that gap.**

**Hard constraint that shapes the whole design:** the economic spine is irreducibly directional
(`Signal.direction` is mandatory; `forward_walk` raises on non-long/short), and a spot/no-options
system has **no standalone non-directional payoff** — you cannot "be long volatility" in spot.
Therefore a non-directional target can only carry economic value **through a directional
consumer**. We do NOT fake a "vol direction" through `forward_walk` (rejected — it conflates
forecast accuracy with P&L and violates the §6.5 Authority Ladder). We measure whether
**conditioning a directional consumer on the regime label improves its OOS expectancy** past the
unchanged M4 gate.

---

## 2. The experiment (hypothesis-free cross-matrix, single pass)

**No mechanism prior.** We do NOT assume "mean-reversion→compression, breakout→expansion." We
pre-register the full **3×3 cross-matrix per consumer**, evaluated in one pass:

```
consumers {mean_reversion, expansion_breakout, spine}  ×  regimes {Compression, Normal, Expansion}
```

Each cell = the consumer's forward-walked outcomes whose **entry-bar regime label** equals that
regime. Every cell goes through the unchanged `EdgeAggregator` + `evaluate_pre_bh` /
`finalize`, and **Benjamini–Hochberg corrects across all real cells in the scope at once** (the
full grid's multiple-testing cost is paid honestly, not hidden). Scopes: per-instrument
(BNB/ETH/BTC/SOL) then POOLED — same order as `qualify_majors`.

### Regime labeler (no-lookahead — load-bearing)
The label at bar *i* is computed from a **trailing window only** (last `tercile_window` ATR
values up to and including bar *i*), classified against that window's own 33.3/66.7 ATR
percentiles → {C, N, E}. It **must not** reuse the production `volatility_regime` global-
percentile rank (F-029) — that is a whole-series statistic and would leak the future into the
target. Bars without a full trailing window are unlabeled and excluded from all cells **and**
from the unconditioned baseline (apples-to-apples).

---

## 3. Controls (four — pre-registered)

A real cell counts only if it beats **all four**. The regime claim's significance is a
**label-permutation test**, not a point comparison: the statistic is
`S = max over regimes of (cell_E − unconditioned_E)` (the best concentration of edge into a
regime), and the null distribution is `S` recomputed over `null_relabelings` seeded random +
shuffled relabelings. The real labeling must satisfy `P(S_null ≥ S_real) ≤ α`. Because the null
maxes over regimes too, this is the honest way to handle "one of three cells might get lucky,"
and it stops a consumer's *unconditioned* edge from masquerading as a *regime* edge.

| # | Control | Guards against | How |
|---|---|---|---|
| a | **Random regime labels** (seeded, empirical-marginal draw) | a lucky 3-way slice any partition would yield | in the null distribution of `S` |
| b | **Shuffled regime labels** (seeded permutation, exact marginal counts) | alignment-free relabeling reproducing the uplift | in the null distribution of `S` |
| c | **Unconditioned consumer** (its own E[R] over the labeled universe) | conditioning must beat *not conditioning* (the F-020 "partitions inflate at large N" lesson) | `S_real > 0` (uplift over unconditioned) |
| d | **Lagged regime labels** `regime(t−k)`, fixed k | **persistence masquerading as forecast skill** — if a stale regime gives equal uplift, you are harvesting `H_atr`, not prediction | `REGIME_REDUNDANT` iff `S_lagged ≥ S_real − redundant_tol` |

---

## 4. Verdict classes (pre-registered before running)

- **`REGIME_EXPLOITABLE`** — some cell clears M4 (all 7 gates incl. cross-matrix BH) **and**
  beats all four controls. The dream outcome; the first positive economic truth. **Only this
  unlocks Stage 4 (Truth Half-Life)** — premature until a positive truth exists.
- **`REGIME_INFORMATIONAL`** — vol predictable but no cell improves directional consumption
  (the expected null given F-020). High-value negative truth → F-030.
- **`REGIME_HARMFUL`** — conditioning *reduces* expectancy (cells worse than unconditioned):
  the memory is real yet *actively misleading* a directional consumer. "Information ≠ useful
  information," strengthening F-020.
- **`REGIME_REDUNDANT`** (sub-case via control d) — current regime beats random but the **lagged**
  regime beats it equally: persistence > 0, **incremental forecast skill = 0**. Collapses into
  INFORMATIONAL for governance; named because it pinpoints the failure *mechanism*.
- **`REGIME_INSUFFICIENT`** (added 2026-06-17, conditioning v1.2) — a consumer whose every regime
  cell fails the sample gate (n < `min_cell_samples`). The cells' sign-counts are noise, so the
  consumer is reported UNDERPOWERED, never HARMFUL/INFORMATIONAL. This is the spine-throughput case
  (~13 trades/instrument → cells of n=1–11; F-019/F-022) — no economic conclusion is drawn from it.

---

## 5. Fixed, pre-committed parameters (anti-archaeology)

These are FROZEN for the single pass. Changing any of them after seeing a null is **forbidden**
(it would make Program 4 into Program 1):

| Parameter | Value | Notes |
|---|---|---|
| `atr_period` | 14 | matches consumers / `process_characterization` |
| `tercile_window` | 480 | ≈ 5 trading days of M15; trailing-only |
| `lag_k` | 50 | the lagged-control staleness (`regime(t−50)`) |
| `min_cell_samples` | 30 | mirrors `q_min_samples`; smaller cells → INSUFFICIENT |
| `harmful_margin` | 0.05 R | cell E below unconditioned by ≥ this ⇒ counts toward HARMFUL |
| `redundant_tol` | 0.05 R | `S_lagged ≥ S_real − this` ⇒ REDUNDANT |
| `null_relabelings` | 200 | random + shuffled draws forming the label-permutation null of `S` |
| exit / cost / OOS / α / permutations | inherited from `research_config_*` | same court as Program 1 |

**Anti-archaeology rule:** if the single pass fails its controls, **STOP**. No tercile-window
grid (20/25/30…), no regime-count change, no extra consumers, no "just one more." The **first
falsification carries authority**.

---

## 6. Calibration gate (instrument validity — run before any economic claim)

Before trusting the harness, confirm the labeler reproduces the known memory: on BNBUSDT, the
`process_characterization` thesis flags `volatility_persistent` (`H_atr>0.55`) and
`volatility_memory_exceeds_direction` must hold. If calibration fails, the instrument/labeler is
invalid and the economic verdict is void (as F-026 did).

---

## 7. Research Envelope

| Axis | This program | Out of scope (would be a new program) |
|---|---|---|
| Target | volatility-regime state {C,N,E} | direction (Program 1, KILLED); structural asymmetry (Program 2) |
| Horizon | M15 | HTF (Program 3, frozen) |
| Universe | crypto majors (frozen data) | FX/metals; non-spot |
| Consumer | existing toys + spine | new entry hypotheses |
| Execution | spot long/short (R-multiple) | options/sizing/inventory (the natural next ontology if INFORMATIONAL) |

---

## 8. Verdict-binding (the now-binding risk is institutional, not statistical)

- The result is registered as **F-030** the same turn it is produced (Validated/Evidence),
  enforced by `tests/test_current_findings.py` — no "let me try one more thing" gap.
- On any null (`INFORMATIONAL` / `HARMFUL` / `REDUNDANT`), Program 4 is **KILLED/FROZEN** in the
  Funding Ledger with Reopen Conditions = "a genuinely new ontology (non-spot execution /
  optionality / state-transition / risk-transfer), **NOT a parameter pass**." Per CLAUDE.md §6.2
  a KILLED/FROZEN initiative may not be silently revived. The fixed parameters in §5 are named
  forbidden reopen routes.
- Authority belongs to the **first** falsification. Run once; accept the verdict.

---

## 9. Pre-drafted F-030 (the expected null, to be confirmed or overturned)

> **F-030** — *Predictable volatility is informational but economically sterile inside spot
> directional architectures* (vol has memory `H_atr≈0.885`, but no regime cell lifts a directional
> consumer's OOS expectancy past M4 against all four controls) → the binding constraint is the
> **execution model**, not predictability. Type GOV/ECON · Confidence: fill on result.

If instead a cell clears all gates+controls: **F-030 flips to `REGIME_EXPLOITABLE`** (first
monetizable truth; advance to shadow measurement under the Authority Ladder — grants tunability,
not production authority, until ΔG001 is demonstrated).
