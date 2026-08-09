# H-RR-THRESHOLD-001 — Production R-threshold study (tp1 × min_rr)

> **PRE-REGISTERED before any outcome measurement on this protocol.**  
> Status: **OPEN · EXPLORATORY_RESEARCH · RESEARCH_ONLY**  
> Date: 2026-07-17 · Branch: `feature/truth-registry-v2` (and successors)  
> User-opened explicitly after RR contract D/SL-TP wiring (2026-07-17).

| Field | Value |
|-------|--------|
| Program alias | **H-RR-THRESHOLD-001** |
| Working title | PRODUCTION_R_THRESHOLD_TP1_AND_MIN_RR |
| Task class | `EXPLORATORY_RESEARCH` |
| Authority | **RESEARCH_ONLY** (§6.5) — never auto-promotes config |
| Production behavior change | **NO** until separate config-governance promote |
| Entry discovery | **NO** — entries fixed |
| Post-hoc threshold mining | **FORBIDDEN** |
| rr_fusion (contract B) re-enable | **FORBIDDEN** in this study |
| Derived from XAUUSD descriptive pack as edge claim | **NO** — pack only motivates *why the knobs are now honest* |

Machine twin: [`h-rr-threshold-001-experiment-definition.json`](h-rr-threshold-001-experiment-definition.json)

Related (do not conflate):
- **F-025** — exit/cost is risk/cost lever, not expectancy (prior; expect null alpha)
- **F-048 / D-wiring 2026-07-17** — true RR from SL/TP; polarity ≠ economic RR
- **`src/research/exit_grid.py`** — reusable measure-only exit re-sim core
- **M4** — `src/research/qualification.py` gate vocabulary (reuse where applicable)

---

## 1. Why this study exists

After wiring **contract D** (`trade_plan["rr_ratio"]` from SL/TP geometry) and leaving **B** shadow-only:

1. **Ultron `min_rr_ratio=1.5`** is an *admission* floor on planned economic R.
2. **CRT `tp1_atr_multiplier*`** sets the *primary target* R used to compute that planned R (and path outcomes if exits follow TP1).
3. Several production intents have **TP1 R &lt; 1.5** (e.g. default `1.0`, pullback `0.8`) and will fail D **honestly**.

That is a **config-governance tension**, not a signal. This study asks whether any **pre-registered closed cell** of `(tp1_R, min_rr)` improves *risk-adjusted path outcomes* or *admission economics* vs the incumbent — without fishing and without touching entry logic.

It does **not** re-open the XAUUSD engine-null pack as an edge claim. Near-miss path structure may appear only as **diagnostic** context after the gate speaks — never as a free search over trailing rules.

---

## 2. Hypotheses (frozen)

### Arm A — Admission filter (Ultron-style min_rr)

**H_A:** On a frozen entry stream, admitting only trades whose **planned TP1 R** ≥ `min_rr` (from CRT-style SL/TP construction) improves OOS mean net-R and/or profit factor of the *admitted* book vs the incumbent admission rule, after costs.

**H_A0:** No pre-registered `min_rr` cell beats the incumbent admission rule on the primary OOS metric after multiple-testing control (or all cells fail absolute E≥0 / PF≥1).

### Arm B — Exit geometry (TP R-multiple)

**H_B:** Holding entries fixed, changing **TP ATR-multiple** (primary target R) over the frozen grid improves OOS mean net-R vs the incumbent TP cell, after costs, under `forward_walk(intrabar_fixed)`.

**H_B0:** No pre-registered TP cell beats the incumbent on primary OOS metric (consistent with F-025: exit is not expectancy alpha).

### Joint (optional, secondary only)

Report the **Cartesian product** of Arm A × Arm B cells as **secondary descriptive tables only** — **not** in the primary BH cohort (avoids combinatorial promotion fishing). Primary promotion authority is **per-arm only**.

---

## 3. Incumbent (frozen baseline)

| Knob | Incumbent value (active `v2_multi_2026_04`) |
|------|-----------------------------------------------|
| `ultron_risk_gate.min_rr_ratio` | **1.5** |
| `crt_engine.tp1_atr_multiplier` (default) | **1.0** |
| `crt_engine.tp1_atr_multiplier_breakout` | **1.5** |
| `crt_engine.tp1_atr_multiplier_pullback` | **0.8** |
| `crt_engine.tp1_atr_multiplier_liq_sweep` | **1.2** |
| `crt_engine.tp1_atr_multiplier_reversal` | **1.0** |
| `crt_engine.tp2_atr_multiplier` | **2.0** (audit / secondary TP only — **not** primary study exit unless listed in grid) |
| `crt_engine.sl_atr_buffer` | **0.2** (SL construction fixed — **not** swept here) |

**Incumbent Arm A rule:** admit if planned TP1 R ≥ **1.5** (current Ultron floor), with planned R from intent’s production tp1 mult.

**Incumbent Arm B cell:** intent’s production `tp1_atr_multiplier_*` (or default 1.0); SL construction fixed as production `sl_atr_buffer` + candle extreme (same as `compute_crt_levels`).

---

## 4. Frozen grids (closed sets — no expansion without new prereg)

### 4.1 Arm A — `min_rr` admission thresholds

| Cell id | min_rr |
|---------|--------|
| A-1.0 | 1.0 |
| A-1.2 | 1.2 |
| A-1.5 | **1.5 (incumbent)** |
| A-2.0 | 2.0 |

**Only these four.** No 1.1, 1.3, 1.7, continuous search, or per-instrument retune inside this prereg.

### 4.2 Arm B — primary TP R-multiples (exit re-sim)

| Cell id | tp_atr_mult (primary target R) |
|---------|--------------------------------|
| B-1.0 | 1.0 |
| B-1.5 | 1.5 |
| B-2.0 | 2.0 |

**SL side fixed** for Arm B: use production-equivalent SL geometry  
(`compute_crt_levels` / incumbent buffer) — **not** the full F-025 SL grid.

**Only these three TP cells.** No 2.5/3.0/4.0 in this program (those belong to broader exit-grid archaeology already covered by F-025).

### 4.3 Explicitly out of scope (forbidden without new prereg)

- Trailing stops, time stops, partials, BE moves  
- Sweeping `sl_atr_buffer` or full SL×TP grid (use F-025 / `exit_grid` for that history)  
- Engine scores / fusion / rr_fusion / polarity as selectors of R cell  
- XAUUSD near-miss MFE rules as exits  
- Per-family free search beyond reporting **diagnostic** breakdowns  
- Changing fusion weights or DecisionEngine score thresholds  

---

## 5. Population & entry stream (frozen before run)

| Item | Value |
|------|--------|
| Primary universe | **CRYPTO_MAJORS** M15: BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT (same class as F-019…F-025) |
| Optional corroboration (non-primary) | XAUUSD M15 — **diagnostic only**, not in BH cohort |
| Entry stream (primary) | Fixed toy/spine entry list already used for exit measurement on this repo: **expansion_breakout + mean_reversion** entry timestamps from the research harness that feeds `exit_grid` / qualify pipelines — **pin exact artifact path + hash at run start** in the result manifest |
| Entry freeze rule | Entries generated **once** under incumbent detection; all R cells re-simulate exits/admission on that list only |
| Costs | **12 bps** round-trip (repo standard CostModel) |
| Exit model | **`intrabar_fixed`** (`forward_walk`) |
| OOS | **70/30 time split** by entry timestamp (IS first 70%, OOS last 30%) — no shuffle |
| Min N | **n≥30** admitted (Arm A) or measured (Arm B) else **INSUFFICIENT** |

If the exact entry artifact cannot be pinned, the run is **BLOCKED** (do not improvise a new entry generator inside this program).

---

## 6. Measurement (pre-registered)

### 6.1 Planned R (admission, Arm A)

For each entry, with candidate `tp1_mult` (from intent map or study cell):

```text
levels = compute_crt_levels(entry, direction, low, high, atr, sl_atr_buffer=0.2, tp1_mult=..., tp2_mult=2.0)
planned_R_tp1 = |tp1 − entry| / |entry − sl|   # equals tp1_mult by construction
admit = planned_R_tp1 >= min_rr
```

### 6.2 Realized path (Arm B and Arm A-admitted books)

```text
net_R = CostModel.net_rr( forward_walk(...).rr_achieved , ... )  # 12 bps
```

Use `src/research/exit_grid.net_rr` / `forward_walk` — no new path math.

### 6.3 Metrics (per cell)

| Metric | Role |
|--------|------|
| n | sample size |
| mean net-R (E) | primary location |
| profit factor (PF) | primary scale |
| win rate | diagnostic |
| MaxDD (R) | risk diagnostic |
| admit_rate (Arm A) | throughput diagnostic |

### 6.4 Primary success criterion (per arm, OOS)

A cell is **candidate-better** than incumbent only if **all** hold on **OOS**:

1. `n ≥ 30`  
2. `E_OOS ≥ 0`  
3. `PF_OOS ≥ 1`  
4. `E_OOS > E_incumbent_OOS` (strict)  
5. 70/30 retention: IS and OOS both E&gt;0 and `E_OOS/E_IS ≥ 0.5` when IS E&gt;0  
6. Permutation p ≤ 0.05 on OOS mean-R vs label-shuffle null within cell (n_perm=**1000**, seed frozen in manifest)

**Multiple testing:** Benjamini–Hochberg FDR **0.05** over the arm’s non-incumbent cells that reach step 6.

**Verdict vocabulary:**

| Verdict | Meaning |
|---------|---------|
| `INSUFFICIENT` | n&lt;30 |
| `REJECT` | fails E/PF/retention/perm or loses to incumbent |
| `REDUNDANT` | passes absolute gates but not strictly better than incumbent |
| `PROMOTE_RESEARCH` | passes all + BH — **research authority only** |
| `ENGINEERING_ONLY` | structural_upper_bound ≤ 0 style outcome (optional; if computed via exit_grid ceilings) — risk shaping not alpha |

**PROMOTE_RESEARCH does not write production config.** Any later config change is a **separate governance promote** with human approval.

---

## 7. Priors (E-001 — recorded before the run)

1. **F-025 prior:** exit geometry is a **risk/cost** lever; expected Arm B outcome = **REJECT / REDUNDANT / ENGINEERING_ONLY**, not expectancy alpha.  
2. **Admission prior:** higher `min_rr` reduces throughput; conditional E may rise while total book E may not — both must be reported; primary is **OOS E of admitted book**, with admit_rate diagnostic.  
3. **D-wiring prior:** fixing honest planned R changes *who fails Ultron*, not market edge.  
4. **Forbidden upgrade:** do not read a PROMOTE_RESEARCH as license to enable rr_fusion or rewrite DecisionEngine polarity.

---

## 8. Execution protocol (when run is authorized)

1. Freeze entry artifact path + sha256 into `results/research/h_rr_threshold_001/manifest.json`.  
2. Implement or call a thin driver under `scripts/research/` that **only** reads the frozen grid from the machine twin JSON (no CLI overrides of the grid).  
3. Write `results/research/h_rr_threshold_001/report.json` + `REPORT.md`.  
4. Mint finding **only after** read (e.g. F-0xx) — number not reserved here.  
5. **STOP** after one full primary-universe run. Corroboration XAUUSD is optional diagnostic, not a second fishing pass.

**Determinism:** sorted instruments/timestamps; RNG seed in manifest; no wall-clock in report body.

---

## 9. Authority ladder (non-optional)

| Outcome | Allowed next step |
|---------|-------------------|
| REJECT / REDUNDANT / INSUFFICIENT | Document; leave production knobs; optional config-governance hygiene only if live ops require alignment |
| PROMOTE_RESEARCH | May **propose** a config PR for human governance; may **not** silent-edit production |
| Live reject spike without this study | Still allowed: pure config review of tp1 vs min_rr **without** claiming expectancy edge |

---

## 10. Epistemic integrity checklist (pre-run)

1. Artifact supporting claims = entry pin + forward_walk + this prereg (file:line in report).  
2. INSUFFICIENT is a valid outcome — do not thin-bin.  
3. Do not upgrade sign noise: BH + OOS required.  
4. Statistical vs economic: E≥0 and PF≥1 are economic floors, not optional.  
5. Parent not stronger than children: Cartesian A×B is secondary only.  
6. After raw counts, prefer under-claim.

Mandatory phrase if overclaim detected:  
> **"Caught me overclaiming; I owe you a correction."**

---

## 11. Status

| Item | State |
|------|--------|
| Design frozen | **YES** (this document + JSON twin) |
| Run executed | **NO** |
| Finding minted | **NO** |
| Production config changed | **NO** |

**Next step to execute:** user authorizes `Implement H-RR-THRESHOLD-001 run` (or equivalent). Until then, design-only.

---

## 12. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Initial open preregistration after user explicit open |
