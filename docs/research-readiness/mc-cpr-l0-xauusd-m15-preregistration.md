# MC-CPR-L0 — Capital Pressure Ratio Level-0 Pre-Registration

**Contract:** [`configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json`](../../configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json)  
**Experiment id:** `E-CPR-L0-XAUUSD-M15`  
**Program binding:** `Program_CPR_L0` (**not** Program 6 carry/basis)  
**Created UTC:** 2026-08-08  
**Status:** PREREGISTERED — `trust_status.mt00=UNRUN`, `economic_claims_allowed=false`  
**Ontology:** UNK-002…UNK-005 (`configs/formulas/market_ontology.yaml`)  
**Charter:** [`docs/governance/MEASUREMENT_CONTRACT.md`](../governance/MEASUREMENT_CONTRACT.md)  
**Profile inheritance (defaults only):** [`configs/research/measurement_contracts/metals_mt5.v1.json`](../../configs/research/measurement_contracts/metals_mt5.v1.json) (`MP-METALS-MT5`) — instance **wins** on all declared fields  

---

## 0. Scope (frozen at prereg)

| Field | Value |
|---|---|
| Instruments | **XAUUSD only** |
| Timeframe | **M15** |
| Clock basis (research) | **UTC** for session-conditioned logic (F-066 control; production CRT filter unchanged) |
| Data source | **OHLCV only** — no tape, no OI, no L2 |
| Execution boundary | **Observe-only research** — no production code path, no fusion weight, no live risk table |
| Authority | **None** until E-MT-00 PASS + E-MT-01 COMPLETE; even then info≠value≠authority |

---

## 1. Latent variables (ontology — not runtime)

| Node | Id | Role in this experiment |
|---|---|---|
| Global Capital | UNK-002 | Latent parent (unobserved) |
| Investment Pool | UNK-003 | BI+SI (unobserved) |
| Directional legs | UNK-004 | BI / SI (unobserved) |
| CPR | UNK-005 | Latent cause; **proxy only** in L0 |

**Identification bound (mandatory honesty):**  
Synthetic BuyPressure/SellPressure are **not** true market BI/SI capital. They are OHLCV **manifestation proxies**. A pass of residual information tests graduates the *proxy* claim, not UNK-005 to PRODUCTION_CERTIFIED.

---

## 2. Synthetic directional pressure {#synthetic-directional-pressure}

Let \(\epsilon = 10^{-12}\), range \(R_t = H_t - L_t + \epsilon\).

\[
\mathrm{BodyRatio}_t = \frac{|C_t - O_t|}{R_t}
\]

\[
\mathrm{BuyPressure}_t = V_t \cdot \frac{C_t - L_t}{R_t}
\]

\[
\mathrm{SellPressure}_t = V_t \cdot \frac{H_t - C_t}{R_t}
\]

**PIT:** computed from bar \(t\) OHLC+V only (bar \(t\) complete).  
**Not equal to:** ontology body_ratio FM path without volume; true BI/SI.

---

## 3. CPR raw proxy {#cpr-raw}

For horizon \(N \in \{4, 16, 96\}\) (1h / 4h / 24h of M15 bars):

\[
\mathrm{CPR\_Raw}_t^{(N)}
=
\frac{\sum_{k=0}^{N-1} \mathrm{BuyPressure}_{t-k}}
{\sum_{k=0}^{N-1} \big(\mathrm{BuyPressure}_{t-k} + \mathrm{SellPressure}_{t-k}\big) + \epsilon}
\]

Requires \(N\) completed prior bars; warmup rows dropped (count in fingerprint).

**Note:** This is a **close-location volume share** on \([0,1]\), not BI/SI currency ratio. Mapping to the illustrative 1:5…5:1 CPR table is **diagnostic only** and not a gate.

---

## 4. CPR z-score {#cpr-z}

\[
\mathrm{CPR\_Z}_t^{(N)}
=
\frac{\mathrm{CPR\_Raw}_t^{(N)} - \mu_{t,M}^{(N)}}{\sigma_{t,M}^{(N)} + \epsilon}
\]

- \(M = 672\) M15 bars (~7×24h of bars; trading-day count is corpus-dependent).  
- \(\mu,\sigma\) = rolling mean/std of \(\mathrm{CPR\_Raw}^{(N)}\) on bars \(\le t\) **excluding** \(E_{\mathrm{event}}=1\) bars from the rolling sample.  
- Primary prereg variant for residual tests: \(N=16\) (pre-registered head); \(N\in\{4,96\}\) are multiplicity-counted variants (3 horizons × 3 targets = 9 tests → BH-FDR).

---

## 5. Residualization protocol {#residualization}

Against active **39-dim v4.0** canonical feature vector \(F_t^{(1..39)}\) at the same PIT:

\[
\mathrm{CPR\_Z}_t^{(N)} = \gamma_0 + \sum_{i=1}^{39} \gamma_i F_{t,i} + \eta_t
\]

- Fit \(\gamma\) on **train** split only; apply to train and test to form \(\hat\eta_t\).  
- **Only \(\hat\eta_t\)** enters L1 predictive tests.  
- Raw CPR association without residualization is **diagnostic**, never a pass.

**Null / pass (L1 information only):**

| Item | Rule |
|---|---|
| \(H_0\) | No OOS association between \(\hat\eta\) and pre-registered targets after BH-FDR |
| Pass | BH \(q < 0.01\) on ≥1 pre-registered (horizon, target) pair **and** residual \(R^2 > 0\) vs 39-dim baseline on OOS |
| **Not** a pass | \(E_{\mathrm{OOS}} > 0\) (economic; forbidden as L1 gate under this contract) |
| Kill | No BH hit **or** residual \(R^2 \le 0\) (rename of existing features) **or** PIT/circularity probe fail |

Permutation null uses split `seed=20260808`.

---

## 6. Targets (information only)

| Id | Definition |
|---|---|
| `fwd_return_1b` | \((C_{t+1}-C_t)/C_t\) |
| `fwd_return_4b` | \((C_{t+4}-C_t)/C_t\) |
| `displacement_continuation` | \(1\) if \(\mathrm{sign}(C_t-O_t)=\mathrm{sign}(C_{t+h}-C_t)\) for \(h\in\{4,16\}\) else \(0\) (prereg: evaluate \(h=4\) primary, \(h=16\) secondary under multiplicity) |

No trade ledger; no `opportunities.*` outcomes.

---

## 7. Circularity & session guards

1. **\(F_t \le t\)** for all rolling stats; optional \(F_t \le t-1\) if a future run declares next-open execution framing.  
2. **Forbidden in CPR features:** same-bar or future return, trade outcome, CRT `TRADE_OPENED`, DecisionEngine scores.  
3. **Session (UTC research anchors only — not production CRT windows):**  
   - Asia: 00:00–08:00 UTC  
   - London: 07:00–16:00 UTC  
   - New York: 12:00–21:00 UTC  
   Session may be used as a **stratification** diagnostic, not as a silent substitute for CPR.  
4. **Events:** tag \(E_{\mathrm{event}}=1\) for scheduled high-impact slots (12:30/13:30 UTC NFP/CPI class); exclude from \(\mu,\sigma\) fitting.  
5. **Production non-touch:** `crt_engine.session_windows` and live risk paths remain unchanged.

---

## 8. Multiplicity (preregistered = 9)

Variants counted under BH-FDR:

- Horizons \(N \in \{4,16,96\}\)  
- Targets: `fwd_return_1b`, `fwd_return_4b`, `displacement_continuation` (primary h=4)

No post-hoc target fishing. Additional diagnostics must be labeled non-gating.

---

## 9. Governance boundary (hard)

| Action | Allowed by this prereg? |
|---|---|
| Seal MC JSON + this doc | Yes (done) |
| Run observe-only residual tests | Yes (future turn) |
| Set `economic_claims_allowed=true` | **No** until E-MT-00/01 complete |
| CPR → fusion / DecisionEngine / Ultron risk% | **No** |
| Blame inverted-SL or zone wiring on CPR | **No** |
| Introduce OI/tape under this contract id | **No** — new `MC-*` required |
| Call this Program 6 | **No** — Program 6 is carry/basis (F-033/F-034) |

---

## 10. E-MT-00 / E-MT-01 (declared, UNRUN)

Evidence paths (PENDING until first run):

- `results/research/mc_cpr_l0/population_fingerprint.PENDING.json`  
- `results/research/mc_cpr_l0/mt00_report.PENDING.json`  
- `results/research/mc_cpr_l0/mt01_coverage.PENDING.json`  

Minimum E-MT-01 classes for this experiment (slice, not full global 27):

| Class theme | Intent |
|---|---|
| Lookahead / PIT | Future bars in CPR roll |
| Feature rename | Skip residualization |
| Label leakage | Use stream outcomes as y for “economic” claim |
| Split leakage | Random non-chrono OOS |
| Pipeline misclaim | Report as fusion-gate result |

---

## 11. Change control

- Any formula change, new horizon, new instrument, or OI/tape → **new contract_id** (do not mutate V1 in place after first fingerprint).  
- V1 may only append evidence paths and trust_status transitions (UNRUN→PASS/FAIL) with audit note.

---

*Observe-only. `PRODUCTION_BEHAVIOR_CHANGED=NO`.*
